use image::{imageops::FilterType, Limits, Rgba, RgbaImage};
use std::env;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const DEFAULT_MAX_WIDTH: u32 = 128;
const DEFAULT_ALPHA_THRESHOLD: u8 = 16;
const MAX_WIDTH: u32 = 512;
const MAX_INPUT_BYTES: u64 = 64 * 1024 * 1024;
const MAX_SOURCE_DIMENSION: u32 = 16_384;
const MAX_DECODE_ALLOCATION: u64 = 128 * 1024 * 1024;
const MAX_OUTPUT_PIXELS: u64 = 262_144;
const MAX_RICH_TEXT_BYTES: usize = 4 * 1024 * 1024;
const MAX_RICH_TEXT_DIMENSION: usize = 4_096;
const MAX_RICH_TEXT_PIXELS: usize = 1_048_576;
const MAX_PREVIEW_DIMENSION: u32 = 8_192;
const MAX_PREVIEW_PIXELS: u64 = 8_388_608;
const DEFAULT_SCALE: u32 = 4;
const MAX_SCALE: u32 = 12;

type RichColor = [u8; 3];
type RichPixel = Option<RichColor>;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Operation {
    ImageToRichText,
    RichTextToImage,
    RichTextPixelArt,
}

struct PixelArt {
    width: u32,
    height: u32,
    pixels: Vec<RichPixel>,
}

#[derive(Clone, Copy)]
enum PreviewBackground {
    Transparent,
    Dark,
    Light,
}

impl PreviewBackground {
    fn pixel(self) -> Rgba<u8> {
        match self {
            Self::Transparent => Rgba([0, 0, 0, 0]),
            Self::Dark => Rgba([16, 21, 31, 255]),
            Self::Light => Rgba([248, 250, 252, 255]),
        }
    }
}

struct GeneratedOutput {
    rich_text: String,
    preview_text: String,
    preview_image: RgbaImage,
    width: u32,
    height: u32,
    visible_pixels: usize,
}

fn argument(args: &[String], name: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].clone())
}

fn parse_operation(value: Option<String>) -> io::Result<Operation> {
    match value.as_deref().unwrap_or("image-to-richtext") {
        "image-to-richtext" => Ok(Operation::ImageToRichText),
        "richtext-to-image" => Ok(Operation::RichTextToImage),
        "richtext-pixel-art" => Ok(Operation::RichTextPixelArt),
        other => Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("未知操作模式: {other}"),
        )),
    }
}

fn parse_width(value: Option<String>) -> io::Result<u32> {
    let parsed = value
        .unwrap_or_else(|| DEFAULT_MAX_WIDTH.to_string())
        .parse::<u32>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "最大宽度必须是整数"))?;
    if !(1..=MAX_WIDTH).contains(&parsed) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("最大宽度必须在 1-{MAX_WIDTH} 之间"),
        ));
    }
    Ok(parsed)
}

fn parse_alpha(value: Option<String>) -> io::Result<u8> {
    let parsed = value
        .unwrap_or_else(|| DEFAULT_ALPHA_THRESHOLD.to_string())
        .parse::<u16>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "透明阈值必须是整数"))?;
    u8::try_from(parsed)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "透明阈值必须在 0-255 之间"))
}

fn parse_scale(value: Option<String>) -> io::Result<u32> {
    let parsed = value
        .unwrap_or_else(|| DEFAULT_SCALE.to_string())
        .parse::<u32>()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "放大倍数必须是整数"))?;
    if !(1..=MAX_SCALE).contains(&parsed) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("放大倍数必须在 1-{MAX_SCALE} 之间"),
        ));
    }
    Ok(parsed)
}

fn parse_background(value: Option<String>) -> io::Result<PreviewBackground> {
    match value.as_deref().unwrap_or("dark") {
        "transparent" => Ok(PreviewBackground::Transparent),
        "dark" => Ok(PreviewBackground::Dark),
        "light" => Ok(PreviewBackground::Light),
        other => Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("未知预览背景: {other}"),
        )),
    }
}

fn parse_hex_color(value: &str) -> Result<RichColor, String> {
    let hex = value
        .trim()
        .trim_matches('"')
        .trim_matches('\'')
        .strip_prefix('#')
        .unwrap_or_else(|| value.trim().trim_matches('"').trim_matches('\''));
    if !hex.bytes().all(|value| value.is_ascii_hexdigit()) {
        return Err(format!("无效颜色值: #{hex}"));
    }
    let digit = |index: usize| {
        u8::from_str_radix(&hex[index..index + 1], 16).map_err(|_| format!("无效颜色值: #{hex}"))
    };
    match hex.len() {
        3 => Ok([digit(0)? * 17, digit(1)? * 17, digit(2)? * 17]),
        6 | 8 => {
            let byte = |index: usize| {
                u8::from_str_radix(&hex[index..index + 2], 16)
                    .map_err(|_| format!("无效颜色值: #{hex}"))
            };
            Ok([byte(0)?, byte(2)?, byte(4)?])
        }
        _ => Err(format!("颜色必须使用 #RGB、#RRGGBB 或 #RRGGBBAA: #{hex}")),
    }
}

fn short_path_hash(path: &Path) -> u32 {
    let mut hash = 2_166_136_261_u32;
    for byte in path.to_string_lossy().as_bytes() {
        hash ^= u32::from(*byte);
        hash = hash.wrapping_mul(16_777_619);
    }
    hash
}

fn safe_stem(path: &Path) -> String {
    let raw = path
        .file_stem()
        .and_then(|value| value.to_str())
        .filter(|value| !value.trim().is_empty())
        .unwrap_or("image");
    let mut stem: String = raw
        .chars()
        .map(|value| {
            if value.is_alphanumeric() || value == '-' || value == '_' {
                value
            } else {
                '_'
            }
        })
        .take(40)
        .collect();
    stem = stem.trim_matches(['_', '-', '.']).to_string();
    if stem.is_empty() {
        stem.push_str("image");
    }
    format!("{stem}-{:08x}", short_path_hash(path))
}

fn unique_run_id() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0)
}

fn target_dimensions(width: u32, height: u32, max_width: u32) -> (u32, u32) {
    if width == 0 || height == 0 {
        return (1, 1);
    }
    let source_pixels = u64::from(width) * u64::from(height);
    let width_scale = f64::from(max_width) / f64::from(width);
    let pixel_scale = (MAX_OUTPUT_PIXELS as f64 / source_pixels as f64).sqrt();
    let scale = width_scale.min(pixel_scale).min(1.0);
    let target_width = ((f64::from(width) * scale).round() as u32).max(1);
    let mut target_height = ((f64::from(height) * scale).round() as u32).max(1);
    while u64::from(target_width) * u64::from(target_height) > MAX_OUTPUT_PIXELS {
        target_height = target_height.saturating_sub(1).max(1);
    }
    (target_width, target_height)
}

fn downsample(image: RgbaImage, max_width: u32) -> RgbaImage {
    let (width, height) = image.dimensions();
    let (target_width, target_height) = target_dimensions(width, height, max_width);
    if (width, height) == (target_width, target_height) {
        image
    } else {
        image::imageops::resize(&image, target_width, target_height, FilterType::Nearest)
    }
}

fn color_tag(red: u8, green: u8, blue: u8) -> String {
    format!("<color=#{red:02X}{green:02X}{blue:02X}>")
}

fn generate_outputs(rgba: &RgbaImage, alpha_threshold: u8) -> GeneratedOutput {
    let (width, height) = rgba.dimensions();
    let pixel_count = width as usize * height as usize;
    let mut rich_text = String::with_capacity((pixel_count * 18).min(8 * 1024 * 1024));
    let mut preview_text = String::with_capacity((width as usize + 1) * height as usize + 128);
    let mut preview_image = RgbaImage::new(width, height);
    let mut visible_pixels = 0usize;
    let mut last_color: Option<[u8; 3]> = None;

    rich_text.push_str("<size=5%><line-height=50%>");
    for y in 0..height {
        for x in 0..width {
            let pixel = rgba.get_pixel(x, y).0;
            if pixel[3] < alpha_threshold {
                rich_text.push(' ');
                preview_text.push(' ');
                last_color = None;
                continue;
            }

            let rgb = [pixel[0], pixel[1], pixel[2]];
            if last_color != Some(rgb) {
                rich_text.push_str(&color_tag(rgb[0], rgb[1], rgb[2]));
                last_color = Some(rgb);
            }
            rich_text.push('█');
            preview_text.push('█');
            preview_image.put_pixel(x, y, Rgba([rgb[0], rgb[1], rgb[2], 255]));
            visible_pixels += 1;
        }
        rich_text.push('\n');
        preview_text.push('\n');
        last_color = None;
    }

    let summary = format!(
        "尺寸: {width} × {height} 像素\n可见像素: {visible_pixels}\n透明阈值: {alpha_threshold}\n"
    );
    GeneratedOutput {
        rich_text,
        preview_text: format!("{summary}\n{preview_text}"),
        preview_image,
        width,
        height,
        visible_pixels,
    }
}

fn add_rich_text_row(rows: &mut Vec<Vec<RichPixel>>) -> Result<(), String> {
    if rows.len() >= MAX_RICH_TEXT_DIMENSION {
        return Err(format!("行数超过 {MAX_RICH_TEXT_DIMENSION} 限制"));
    }
    rows.push(Vec::new());
    Ok(())
}

fn apply_rich_text_tag(
    tag: &str,
    colors: &mut Vec<RichColor>,
    rows: &mut Vec<Vec<RichPixel>>,
) -> Result<(), String> {
    let normalized = tag.trim().to_ascii_lowercase();
    if normalized.is_empty() {
        return Err("发现空标签 <>".to_string());
    }
    if matches!(normalized.as_str(), "/color" | "/colour" | "/textcolor") {
        if colors.len() <= 1 {
            return Err("发现多余的 </color> 结束标签".to_string());
        }
        colors.pop();
        return Ok(());
    }
    if matches!(
        normalized.as_str(),
        "/size" | "/line-height" | "/lineheight"
    ) {
        return Ok(());
    }
    if normalized.starts_with("size")
        || normalized.starts_with("line-height")
        || normalized.starts_with("lineheight")
    {
        return Ok(());
    }
    if normalized == "br" || normalized == "br/" || normalized == "br /" {
        return add_rich_text_row(rows);
    }
    if let Some((key, value)) = normalized.split_once('=') {
        if matches!(key.trim(), "color" | "colour" | "textcolor") {
            colors.push(parse_hex_color(value)?);
            return Ok(());
        }
    }
    Err(format!("不支持或格式错误的标签: <{tag}>"))
}

fn parse_rich_text(text: &str) -> Result<PixelArt, String> {
    if text.trim().is_empty() {
        return Err("请粘贴富文本像素画内容".to_string());
    }
    if text.len() > MAX_RICH_TEXT_BYTES {
        return Err(format!(
            "富文本超过 {} MB 限制",
            MAX_RICH_TEXT_BYTES / 1024 / 1024
        ));
    }

    let source = text.trim_start_matches('\u{feff}');
    let mut rows: Vec<Vec<RichPixel>> = vec![Vec::new()];
    let mut colors = vec![[255, 255, 255]];
    let mut parsed_pixels = 0usize;
    let mut index = 0usize;

    while index < source.len() {
        let character = source[index..]
            .chars()
            .next()
            .ok_or_else(|| "富文本包含无效 UTF-8 字符".to_string())?;
        let next = index + character.len_utf8();
        if character == '<' {
            let relative_end = source[next..]
                .find('>')
                .ok_or_else(|| "富文本标签缺少 > 结束符".to_string())?;
            let end = next + relative_end;
            apply_rich_text_tag(&source[next..end], &mut colors, &mut rows)?;
            index = end + 1;
            continue;
        }

        match character {
            '\n' => add_rich_text_row(&mut rows)?,
            '\r' => {
                if !source[next..].starts_with('\n') {
                    add_rich_text_row(&mut rows)?;
                }
            }
            '█' | '■' => {
                let row = rows.last_mut().expect("rows always contains current row");
                if row.len() >= MAX_RICH_TEXT_DIMENSION {
                    return Err(format!("单行像素超过 {MAX_RICH_TEXT_DIMENSION} 限制"));
                }
                row.push(Some(
                    *colors.last().expect("default color is always present"),
                ));
                parsed_pixels += 1;
            }
            value if value.is_whitespace() => {
                let row = rows.last_mut().expect("rows always contains current row");
                if row.len() >= MAX_RICH_TEXT_DIMENSION {
                    return Err(format!("单行像素超过 {MAX_RICH_TEXT_DIMENSION} 限制"));
                }
                row.push(None);
                parsed_pixels += 1;
            }
            other => {
                return Err(format!(
                    "发现不支持的字符 {other:?}，请只使用 █、■、空格、换行和受支持的标签"
                ));
            }
        }
        if parsed_pixels > MAX_RICH_TEXT_PIXELS {
            return Err(format!("像素总数超过 {MAX_RICH_TEXT_PIXELS} 限制"));
        }
        index = next;
    }

    while rows
        .first()
        .is_some_and(|row| row.iter().all(Option::is_none))
    {
        rows.remove(0);
    }
    while rows
        .last()
        .is_some_and(|row| row.iter().all(Option::is_none))
    {
        rows.pop();
    }
    if rows.is_empty() || rows.iter().all(|row| row.iter().all(Option::is_none)) {
        return Err("没有找到可预览的 █ 或 ■ 像素块".to_string());
    }

    let width = rows.iter().map(Vec::len).max().unwrap_or(0);
    let height = rows.len();
    if width == 0 || width > MAX_RICH_TEXT_DIMENSION || height > MAX_RICH_TEXT_DIMENSION {
        return Err("像素画尺寸超出限制".to_string());
    }
    let mut pixels = Vec::with_capacity(width * height);
    for mut row in rows {
        row.resize(width, None);
        pixels.extend(row);
    }
    Ok(PixelArt {
        width: width as u32,
        height: height as u32,
        pixels,
    })
}

fn effective_preview_scale(width: u32, height: u32, requested_scale: u32) -> u32 {
    let longest = width.max(height);
    let dimension_limit = (MAX_PREVIEW_DIMENSION / longest).max(1);
    let pixel_limit_scale = ((MAX_PREVIEW_PIXELS as f64
        / (u64::from(width) * u64::from(height)) as f64)
        .sqrt()
        .floor() as u32)
        .max(1);
    requested_scale
        .min(MAX_SCALE)
        .min(dimension_limit)
        .min(pixel_limit_scale)
}

fn render_rich_text_preview(
    art: &PixelArt,
    requested_scale: u32,
    background: PreviewBackground,
) -> RgbaImage {
    let scale = effective_preview_scale(art.width, art.height, requested_scale);
    let width = art.width * scale;
    let height = art.height * scale;
    let background_pixel = background.pixel();
    let mut output = RgbaImage::new(width, height);

    for source_y in 0..art.height {
        for source_x in 0..art.width {
            let source_index = (source_y * art.width + source_x) as usize;
            let pixel = match art.pixels[source_index] {
                Some(color) => Rgba([color[0], color[1], color[2], 255]),
                None => background_pixel,
            };
            for offset_y in 0..scale {
                for offset_x in 0..scale {
                    output.put_pixel(
                        source_x * scale + offset_x,
                        source_y * scale + offset_y,
                        pixel,
                    );
                }
            }
        }
    }
    output
}

fn pixel_art_to_image(art: &PixelArt) -> RgbaImage {
    RgbaImage::from_fn(art.width, art.height, |x, y| {
        match art.pixels[(y * art.width + x) as usize] {
            Some(color) => Rgba([color[0], color[1], color[2], 255]),
            None => Rgba([0, 0, 0, 0]),
        }
    })
}

fn decode_image(input: &Path) -> io::Result<RgbaImage> {
    let metadata = fs::metadata(input)?;
    if metadata.len() > MAX_INPUT_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!("输入图片超过 {} MB 限制", MAX_INPUT_BYTES / 1024 / 1024),
        ));
    }
    let format = image::ImageFormat::from_path(input).map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("无法识别图片格式: {error}"),
        )
    })?;
    if !matches!(
        format,
        image::ImageFormat::Png
            | image::ImageFormat::Jpeg
            | image::ImageFormat::WebP
            | image::ImageFormat::Bmp
            | image::ImageFormat::Gif
    ) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "仅支持 PNG / JPEG / WebP / BMP / GIF",
        ));
    }

    let mut reader = image::ImageReader::open(input)?;
    reader.set_format(format);
    let mut limits = Limits::default();
    limits.max_image_width = Some(MAX_SOURCE_DIMENSION);
    limits.max_image_height = Some(MAX_SOURCE_DIMENSION);
    limits.max_alloc = Some(MAX_DECODE_ALLOCATION);
    reader.limits(limits);
    reader
        .decode()
        .map(|image| image.to_rgba8())
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error.to_string()))
}

fn process(
    input: &Path,
    output_dir: &Path,
    max_width: u32,
    alpha_threshold: u8,
) -> io::Result<(PathBuf, PathBuf, PathBuf, GeneratedOutput)> {
    let rgba = downsample(decode_image(input)?, max_width);
    let generated = generate_outputs(&rgba, alpha_threshold);
    fs::create_dir_all(output_dir)?;

    let stem = safe_stem(input);
    let run_id = unique_run_id();
    let rich_path = output_dir.join(format!("{stem}-{run_id}_richtext.txt"));
    let preview_path = output_dir.join(format!("{stem}-{run_id}_preview.txt"));
    let preview_image_path = output_dir.join(format!("{stem}-{run_id}_preview.png"));
    fs::write(&rich_path, generated.rich_text.as_bytes())?;
    fs::write(&preview_path, generated.preview_text.as_bytes())?;
    generated
        .preview_image
        .save_with_format(&preview_image_path, image::ImageFormat::Png)
        .map_err(|error| io::Error::other(error.to_string()))?;

    Ok((rich_path, preview_path, preview_image_path, generated))
}

fn process_rich_text(
    text: &str,
    output_dir: &Path,
    scale: u32,
    background: PreviewBackground,
    normalize: bool,
) -> io::Result<Vec<PathBuf>> {
    let art =
        parse_rich_text(text).map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    fs::create_dir_all(output_dir)?;
    let run_id = unique_run_id();

    if normalize {
        let source_image = pixel_art_to_image(&art);
        let generated = generate_outputs(&source_image, 0);
        let stem = format!("richtext-pixel-art-{run_id}");
        let rich_path = output_dir.join(format!("{stem}_richtext.txt"));
        let preview_path = output_dir.join(format!("{stem}_preview.txt"));
        let preview_image_path = output_dir.join(format!("{stem}_preview.png"));
        let scaled_preview = render_rich_text_preview(&art, scale, background);
        fs::write(&rich_path, generated.rich_text.as_bytes())?;
        fs::write(&preview_path, generated.preview_text.as_bytes())?;
        scaled_preview
            .save_with_format(&preview_image_path, image::ImageFormat::Png)
            .map_err(|error| io::Error::other(error.to_string()))?;
        println!(
            "[+] 富文本像素画 {} × {} 像素\n    规范富文本: {}\n    字符预览: {}\n    彩色预览: {}",
            art.width,
            art.height,
            rich_path.display(),
            preview_path.display(),
            preview_image_path.display()
        );
        Ok(vec![rich_path, preview_path, preview_image_path])
    } else {
        let preview = render_rich_text_preview(&art, scale, background);
        let output_path = output_dir.join(format!("richtext-pixel-art-{run_id}.png"));
        preview
            .save_with_format(&output_path, image::ImageFormat::Png)
            .map_err(|error| io::Error::other(error.to_string()))?;
        println!(
            "[+] 富文本 {} × {} 像素 -> {} × {} PNG: {}",
            art.width,
            art.height,
            preview.width(),
            preview.height(),
            output_path.display()
        );
        Ok(vec![output_path])
    }
}

fn run() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    let output = argument(&args, "-o")
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 -o 输出目录"))?;
    let operation = parse_operation(argument(&args, "--mode"))?;

    match operation {
        Operation::ImageToRichText => {
            let input = argument(&args, "-i")
                .filter(|value| !value.is_empty())
                .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 -i 输入图片"))?;
            let max_width = parse_width(argument(&args, "--max-width"))?;
            let alpha_threshold = parse_alpha(argument(&args, "--alpha-threshold"))?;
            let input_path = Path::new(&input);
            let (rich_path, preview_path, preview_image_path, generated) =
                process(input_path, Path::new(&output), max_width, alpha_threshold)?;
            println!(
                "[+] {} -> {} × {} 像素，{} 个可见像素\n    主文本: {}\n    副文本: {}\n    图片预览: {}",
                input_path.display(),
                generated.width,
                generated.height,
                generated.visible_pixels,
                rich_path.display(),
                preview_path.display(),
                preview_image_path.display()
            );
        }
        Operation::RichTextToImage | Operation::RichTextPixelArt => {
            let text = argument(&args, "--text")
                .filter(|value| !value.trim().is_empty())
                .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 --text 富文本"))?;
            let scale = parse_scale(argument(&args, "--scale"))?;
            let background = parse_background(argument(&args, "--background"))?;
            process_rich_text(
                &text,
                Path::new(&output),
                scale,
                background,
                operation == Operation::RichTextPixelArt,
            )?;
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("像素富文本工坊执行失败: {error}");
        eprintln!(
            "用法: image-pixel-richtext --mode image-to-richtext|richtext-to-image|richtext-pixel-art -o <outputDir> [选项]"
        );
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rich_pixel(art: &PixelArt, x: u32, y: u32) -> RichPixel {
        art.pixels[(y * art.width + x) as usize]
    }

    #[test]
    fn converts_pixels_and_applies_alpha_threshold() {
        let mut image = RgbaImage::new(3, 1);
        image.put_pixel(0, 0, Rgba([255, 0, 0, 255]));
        image.put_pixel(1, 0, Rgba([0, 0, 255, 15]));
        image.put_pixel(2, 0, Rgba([0, 0, 255, 16]));

        let output = generate_outputs(&image, 16);
        assert_eq!(
            output.rich_text,
            "<size=5%><line-height=50%><color=#FF0000>█ <color=#0000FF>█\n"
        );
        assert_eq!(output.visible_pixels, 2);
        assert_eq!(output.preview_image.get_pixel(1, 0).0[3], 0);
        assert_eq!(output.preview_image.get_pixel(2, 0).0, [0, 0, 255, 255]);
    }

    #[test]
    fn constrains_width_and_total_preview_pixels() {
        assert_eq!(target_dimensions(1000, 2000, 128), (128, 256));
        let (width, height) = target_dimensions(1000, 100_000, 512);
        assert!(u64::from(width) * u64::from(height) <= MAX_OUTPUT_PIXELS);
    }

    #[test]
    fn output_names_are_safe_and_unique_for_unicode_and_duplicate_stems() {
        let first = safe_stem(Path::new(r"C:\one\像素.png"));
        let second = safe_stem(Path::new(r"C:\two\像素.png"));
        assert!(first.starts_with("像素-"));
        assert_ne!(first, second);
        assert!(!first.contains('\\'));
        assert!(!first.contains('/'));
    }

    #[test]
    fn parses_nested_rich_text_colors_and_pixels() {
        let art = parse_rich_text(
            "<size=5%><line-height=50%><color=#FF0000>█<color=#00FF00>██</color>█</color>\n <color=#0000FF>■",
        )
        .unwrap();
        assert_eq!((art.width, art.height), (4, 2));
        assert_eq!(rich_pixel(&art, 0, 0), Some([255, 0, 0]));
        assert_eq!(rich_pixel(&art, 1, 0), Some([0, 255, 0]));
        assert_eq!(rich_pixel(&art, 2, 0), Some([0, 255, 0]));
        assert_eq!(rich_pixel(&art, 3, 0), Some([255, 0, 0]));
        assert_eq!(rich_pixel(&art, 0, 1), None);
        assert_eq!(rich_pixel(&art, 1, 1), Some([0, 0, 255]));
        assert_eq!(rich_pixel(&art, 3, 1), None);
    }

    #[test]
    fn renders_rich_text_with_scale_background_and_pixel_limits() {
        let art = parse_rich_text("<color=#123456>█").unwrap();
        let preview = render_rich_text_preview(&art, 2, PreviewBackground::Dark);
        assert_eq!((preview.width(), preview.height()), (2, 2));
        assert_eq!(preview.get_pixel(0, 0).0, [0x12, 0x34, 0x56, 255]);
        assert_eq!(effective_preview_scale(1_000, 1_000, 12), 2);
    }

    #[test]
    fn rejects_untrusted_rich_text_characters_and_tags() {
        assert!(parse_rich_text("hello").is_err());
        assert!(parse_rich_text("</color>█").is_err());
        assert!(parse_rich_text("<unknown>█").is_err());
    }
}
