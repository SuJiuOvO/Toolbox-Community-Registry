use png::{BitDepth, ColorType as PngColorType};
use std::env;
use std::fs::{self, File};
use std::io::{self, BufWriter};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_TEXT_BYTES: usize = 4 * 1024 * 1024;
const MAX_SOURCE_DIMENSION: usize = 4_096;
const MAX_SOURCE_PIXELS: usize = 1_048_576;
const MAX_OUTPUT_DIMENSION: u32 = 8_192;
const MAX_OUTPUT_PIXELS: u64 = 8_388_608;
const MAX_SCALE: u32 = 12;
const DEFAULT_SCALE: u32 = 4;

type Color = [u8; 3];
type Pixel = Option<Color>;

struct PixelArt {
    width: u32,
    height: u32,
    pixels: Vec<Pixel>,
}

struct Preview {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

#[derive(Clone, Copy)]
enum Background {
    Transparent,
    Dark,
    Light,
}

impl Background {
    fn pixel(self) -> [u8; 4] {
        match self {
            Self::Transparent => [0, 0, 0, 0],
            Self::Dark => [16, 21, 31, 255],
            Self::Light => [248, 250, 252, 255],
        }
    }
}

fn argument(args: &[String], name: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].clone())
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

fn parse_background(value: Option<String>) -> io::Result<Background> {
    match value.as_deref().unwrap_or("dark") {
        "transparent" => Ok(Background::Transparent),
        "dark" => Ok(Background::Dark),
        "light" => Ok(Background::Light),
        other => Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("未知预览背景: {other}"),
        )),
    }
}

fn parse_hex_color(value: &str) -> Result<Color, String> {
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

fn add_row(rows: &mut Vec<Vec<Pixel>>) -> Result<(), String> {
    if rows.len() >= MAX_SOURCE_DIMENSION {
        return Err(format!("行数超过 {MAX_SOURCE_DIMENSION} 限制"));
    }
    rows.push(Vec::new());
    Ok(())
}

fn apply_tag(tag: &str, colors: &mut Vec<Color>, rows: &mut Vec<Vec<Pixel>>) -> Result<(), String> {
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
        return add_row(rows);
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
    if text.len() > MAX_TEXT_BYTES {
        return Err(format!(
            "富文本超过 {} MB 限制",
            MAX_TEXT_BYTES / 1024 / 1024
        ));
    }

    let source = text.trim_start_matches('\u{feff}');
    let mut rows: Vec<Vec<Pixel>> = vec![Vec::new()];
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
            apply_tag(&source[next..end], &mut colors, &mut rows)?;
            index = end + 1;
            continue;
        }

        match character {
            '\n' => add_row(&mut rows)?,
            '\r' => {
                if !source[next..].starts_with('\n') {
                    add_row(&mut rows)?;
                }
            }
            '█' | '■' => {
                let row = rows.last_mut().expect("rows always contains current row");
                if row.len() >= MAX_SOURCE_DIMENSION {
                    return Err(format!("单行像素超过 {MAX_SOURCE_DIMENSION} 限制"));
                }
                row.push(Some(
                    *colors.last().expect("default color is always present"),
                ));
                parsed_pixels += 1;
            }
            value if value.is_whitespace() => {
                let row = rows.last_mut().expect("rows always contains current row");
                if row.len() >= MAX_SOURCE_DIMENSION {
                    return Err(format!("单行像素超过 {MAX_SOURCE_DIMENSION} 限制"));
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
        if parsed_pixels > MAX_SOURCE_PIXELS {
            return Err(format!("像素总数超过 {MAX_SOURCE_PIXELS} 限制"));
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
    if width == 0 || width > MAX_SOURCE_DIMENSION || height > MAX_SOURCE_DIMENSION {
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

fn effective_scale(width: u32, height: u32, requested_scale: u32) -> u32 {
    let longest = width.max(height);
    let dimension_limit = (MAX_OUTPUT_DIMENSION / longest).max(1);
    let pixel_limit_scale = ((MAX_OUTPUT_PIXELS as f64
        / (u64::from(width) * u64::from(height)) as f64)
        .sqrt()
        .floor() as u32)
        .max(1);
    requested_scale
        .min(MAX_SCALE)
        .min(dimension_limit)
        .min(pixel_limit_scale)
}

fn render_preview(art: &PixelArt, requested_scale: u32, background: Background) -> Preview {
    let scale = effective_scale(art.width, art.height, requested_scale);
    let width = art.width * scale;
    let height = art.height * scale;
    let background_pixel = background.pixel();
    let mut pixels = Vec::with_capacity((width as usize) * (height as usize) * 4);

    for source_y in 0..art.height {
        for _ in 0..scale {
            for source_x in 0..art.width {
                let source_index = (source_y * art.width + source_x) as usize;
                let foreground = match art.pixels[source_index] {
                    Some(color) => [color[0], color[1], color[2], 255],
                    None => background_pixel,
                };
                for _ in 0..scale {
                    pixels.extend_from_slice(&foreground);
                }
            }
        }
    }
    Preview {
        width,
        height,
        pixels,
    }
}

fn unique_output_name() -> String {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    format!("richtext_pixel_preview_{timestamp}.png")
}

fn write_png(path: &Path, preview: &Preview) -> io::Result<()> {
    let file = File::create(path)?;
    let writer = BufWriter::new(file);
    let mut encoder = png::Encoder::new(writer, preview.width, preview.height);
    encoder.set_color(PngColorType::Rgba);
    encoder.set_depth(BitDepth::Eight);
    let mut png_writer = encoder
        .write_header()
        .map_err(|error| io::Error::other(error.to_string()))?;
    png_writer
        .write_image_data(&preview.pixels)
        .map_err(|error| io::Error::other(error.to_string()))?;
    png_writer
        .finish()
        .map_err(|error| io::Error::other(error.to_string()))
}

fn run() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    let text = argument(&args, "--text")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 --text 富文本"))?;
    let output = argument(&args, "-o")
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 -o 输出目录"))?;
    let requested_scale = parse_scale(argument(&args, "--scale"))?;
    let background = parse_background(argument(&args, "--background"))?;
    let art = parse_rich_text(&text)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    let preview = render_preview(&art, requested_scale, background);

    fs::create_dir_all(&output)?;
    let output_path = Path::new(&output).join(unique_output_name());
    write_png(&output_path, &preview)?;
    println!(
        "[+] 富文本 {} × {} 像素 -> {} × {} PNG: {}",
        art.width,
        art.height,
        preview.width,
        preview.height,
        output_path.display()
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("富文本像素预览失败: {error}");
        eprintln!(
            "用法: richtext-pixel-viewer --text <richText> -o <outputDir> [--scale 1-12] [--background dark|light|transparent]"
        );
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pixel(art: &PixelArt, x: u32, y: u32) -> Pixel {
        art.pixels[(y * art.width + x) as usize]
    }

    #[test]
    fn parses_nested_colors_blocks_spaces_and_newlines() {
        let art = parse_rich_text(
            "<size=5%><line-height=50%><color=#FF0000>█<color=#00FF00>██</color>█</color>\n <color=#0000FF>■",
        )
        .unwrap();
        assert_eq!((art.width, art.height), (4, 2));
        assert_eq!(pixel(&art, 0, 0), Some([255, 0, 0]));
        assert_eq!(pixel(&art, 1, 0), Some([0, 255, 0]));
        assert_eq!(pixel(&art, 2, 0), Some([0, 255, 0]));
        assert_eq!(pixel(&art, 3, 0), Some([255, 0, 0]));
        assert_eq!(pixel(&art, 0, 1), None);
        assert_eq!(pixel(&art, 1, 1), Some([0, 0, 255]));
        assert_eq!(pixel(&art, 3, 1), None);
    }

    #[test]
    fn renders_scale_and_background() {
        let art = parse_rich_text("<color=#123456>█").unwrap();
        let preview = render_preview(&art, 2, Background::Dark);
        assert_eq!((preview.width, preview.height), (2, 2));
        assert_eq!(&preview.pixels[0..4], &[0x12, 0x34, 0x56, 255]);
        assert_eq!(effective_scale(1_000, 1_000, 12), 2);
    }

    #[test]
    fn rejects_untrusted_characters_and_extra_color_terminators() {
        assert!(parse_rich_text("hello").is_err());
        assert!(parse_rich_text("</color>█").is_err());
    }
}
