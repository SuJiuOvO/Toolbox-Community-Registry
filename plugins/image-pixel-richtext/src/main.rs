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

fn run() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    let input = argument(&args, "-i")
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 -i 输入图片"))?;
    let output = argument(&args, "-o")
        .filter(|value| !value.is_empty())
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "缺少 -o 输出目录"))?;
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
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("图片像素转换失败: {error}");
        eprintln!(
            "用法: image-pixel-richtext -i <input> -o <outputDir> [--max-width 1-512] [--alpha-threshold 0-255]"
        );
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
