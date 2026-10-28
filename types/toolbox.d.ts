/**
 * Multi-Toolbox Plugin Host Bridge API Definitions
 * 
 * 适用于 Multi-Toolbox QuickJS 动态插件的官方 TypeScript 类型声明。
 * 开发者在插件 JavaScript (entry.js) 顶部声明以下三斜线指令即可在 VS Code / WebStorm 中获得完整的智能补全：
 * /// <reference path="../../types/toolbox.d.ts" />
 *
 * @version 2.4.0
 */

declare namespace ToolboxAPI {
  /**
   * 图像管道流水线操作步骤定义
   */
  export type ImagePipelineStep =
    | {
        op: 'canvas' | 'create';
        width: number;
        height: number;
        color?: string; // 默认 'transparent'，支持 '#RRGGBB' 或 '#RRGGBBAA'
      }
    | {
        op: 'resize';
        width?: number;
        w?: number;
        height?: number;
        h?: number;
      }
    | {
        op: 'crop';
        x: number;
        y: number;
        width: number;
        height: number;
      }
    | {
        op: 'circle_crop';
      }
    | {
        op: 'flip' | 'flip_h' | 'flip_v';
        direction?: 'horizontal' | 'vertical';
      }
    | {
        op: 'overlay' | 'composite';
        image?: string; // 图像文件路径
        base64?: string; // Base64 编码的图像数据
        x?: number;
        dstX?: number;
        y?: number;
        dstY?: number;
        width?: number;
        w?: number;
        height?: number;
        h?: number;
      }
    | {
        op: 'init_gif';
        fps?: number; // 默认 10 帧/秒
        repeat?: number; // 默认 0 循环
        output: string; // 输出 gif 文件名或路径
      }
    | {
        op: 'add_gif_frame';
      }
    | {
        op: 'load';
        file?: string;
        path?: string;
      }
    | {
        op: 'save' | 'encode';
        format: 'png' | 'jpg' | 'jpeg' | 'gif';
        output: string;
        quality?: number; // 1 - 100
      };

  /**
   * 异步 HTTP 请求选项 (兼容 Fetch API)
   */
  export interface HttpRequestOptions {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'HEAD' | string;
    headers?: Record<string, string>;
    body?: string | Record<string, any> | any[] | Uint8Array;
  }

  /**
   * 现代异步 HTTP 响应对象 (兼容 Fetch Response 规范)
   */
  export interface HttpResponse {
    /** HTTP 状态码是否在 200~299 范围内 */
    readonly ok: boolean;
    /** HTTP 状态码 (例如 200, 404, 500) */
    readonly status: number;
    /** 状态码别名 */
    readonly statusCode: number;
    /** 状态文本 (例如 "OK", "Error") */
    readonly statusText: string;
    /** 响应头字典 */
    readonly headers: Record<string, string>;
    /** 响应体文本内容 */
    readonly body: string;
    /** 将响应体解析为 JSON 结构 */
    json<T = any>(): Promise<T>;
    /** 将响应体解析为纯文本 */
    text(): Promise<string>;
  }

  /**
   * 同步 HTTP 响应对象 (向后兼容)
   */
  export interface SyncHttpResponse {
    readonly statusCode: number;
    readonly body: string;
  }

  /**
   * WebAssembly 模块导出检查报告
   */
  export interface WasmInspectReport {
    functions: Array<{ name: string; params: string[]; results: string[] }>;
    memories: any[];
    globals: any[];
    tables: any[];
  }

  /**
   * WebAssembly 执行结果
   */
  export interface WasmCallResult {
    success: boolean;
    result?: any;
    error?: string;
    executionTimeMs?: number;
  }

  /**
   * 归档解压与压缩处理结果
   */
  export interface ArchiveResult {
    success: boolean;
    message: string;
    outputFiles: string[];
  }

  /**
   * 图像流水线处理结果
   */
  export interface ImagePipelineResult {
    success: boolean;
    message: string;
    outputFiles: string[];
  }

  /**
   * 插件执行上下文参数
   */
  export interface PluginRunContext<TParams = Record<string, any>> {
    /** 用户选取的输入文件绝对路径列表 */
    inputFiles: string[];
    /** 宿主提供的输出结果专属落盘目录 */
    outputDir: string;
    /** 动态表单配置填写的参数键值对 */
    params: TParams;
  }

  /**
   * 插件标准执行返回契约
   */
  export interface PluginResult {
    /** 任务是否执行成功 */
    success: boolean;
    /** 状态提示信息，呈现给用户的通知文字 */
    message?: string;
    /** 结构化数据输出，键名与 manifest.json 中的 outputs[].id 对应 */
    data?: Record<string, any> | any;
    /** 纯文本输出 (copyable_text) */
    text?: string;
    /** 输出的文件列表 */
    files?: string[];
  }

  /**
   * 宿主环境变量
   */
  export interface HostEnvironment {
    outputDir: string;
    inputFiles: string[];
    params: Record<string, any>;
    platform: 'windows' | 'android' | 'other';
  }

  /**
   * 宿主文件系统 (Toolbox.fs) API
   */
  export interface FileSystemAPI {
    /** 读取指定文件的 UTF-8 文本或 Base64 编码 */
    readFile(path: string, isBase64?: boolean): string;
    /** 以 Uint8Array 二进制字节数组形式直接读取文件（处理音视频与图片推荐） */
    readBytes(path: string): Uint8Array;
    /** 读取指定文件的 UTF-8 纯文本 */
    readText(path: string): string;
    /** 写入文本或 Base64 编码的二进制到指定路径 */
    writeFile(path: string, content: string, isBase64?: boolean): boolean;
    /** 检查指定路径的文件或目录是否存在 */
    exists(path: string): boolean;
    /** 列出指定目录下的文件与子目录名称 */
    listFiles(path: string): string[];
    /** 递归创建目录 */
    mkdir(path: string): boolean;
    /** 删除指定文件或递归删除目录 */
    remove(path: string): boolean;
    /** 删除指定文件或递归删除目录 (remove 别名) */
    delete(path: string): boolean;
    /** 获取文件大小 (字节数) */
    fileSize(path: string): number;
  }

  /**
   * 插件专属持久化数据存储 (Toolbox.storage) API
   */
  export interface StorageAPI {
    /** 获取存储的配置项 */
    get<T = any>(key: string, defaultValue?: T): T;
    /** 写入持久化配置项（跨生命周期生效） */
    set(key: string, value: any): boolean;
    /** 移除指定的配置项 */
    remove(key: string): boolean;
    /** 移除指定的配置项 (remove 别名) */
    delete(key: string): boolean;
    /** 获取当前插件持久化的所有键值对字典 */
    getAll(): Record<string, any>;
  }

  /**
   * 极速数据转换工具箱 (Toolbox.utils) API
   */
  export interface UtilsAPI {
    /** 将 Base64 字符串快速无损解码为 Uint8Array 二进制字节数组 */
    base64ToBytes(b64: string): Uint8Array;
    /** 将 Uint8Array 二进制字节数组快速编码为 Base64 字符串 */
    bytesToBase64(bytes: Uint8Array): string;
  }

  /**
   * 安全散列与编解码 (Toolbox.crypto) API
   */
  export interface CryptoAPI {
    /** 计算纯文本的 MD5 散列值 */
    md5(text: string): string;
    /** 计算纯文本的 SHA-256 散列值 */
    sha256(text: string): string;
    /** 对纯文本进行 Base64 编码 */
    base64Encode(text: string): string;
    /** 对 Base64 密文进行解码为 UTF-8 文本 */
    base64Decode(text: string): string;
  }

  /**
   * 归档与压缩解包 (Toolbox.archive) API
   */
  export interface ArchiveAPI {
    /** 解压指定的压缩包到指定目录（支持 zip, 7z, rar, tar, gz 等） */
    extract(archivePath: string, outputDir?: string, password?: string): Promise<ArchiveResult>;
    /** 将指定的文件或目录列表压缩为归档文件 */
    compress(inputPaths: string[], outputPath?: string, format?: 'zip' | '7z'): Promise<ArchiveResult>;
  }

  /**
   * 原生图像流水线 (Toolbox.image) API
   */
  export interface ImageAPI {
    /**
     * 调度宿主纯 Dart 驱动的高性能多通道图像处理管道
     * 支持多步操作连续变换、抗锯齿缩放、图层叠放加水印与 GIF 动图量化生成
     */
    pipeline(steps: ImagePipelineStep[], inputFiles?: string[]): Promise<ImagePipelineResult>;
  }

  /**
   * WebAssembly 沙箱算力 (Toolbox.wasm) API
   */
  export interface WasmAPI {
    /** 检查 WASM 二进制模块导出的函数签名与内存定义 */
    inspect(wasmSource: string | Uint8Array): Promise<WasmInspectReport>;
    /** 调用 WASM 模块中导出的纯计算函数 */
    call(wasmSource: string | Uint8Array, functionName: string, args?: any[]): Promise<WasmCallResult>;
  }

  /**
   * 网络请求 (Toolbox.http) API
   */
  export interface HttpAPI {
    /** 现代标准 Promise 非阻塞网络请求 (推荐首选) */
    fetch(url: string, options?: HttpRequestOptions): Promise<HttpResponse>;
    /** 标准异步 GET 请求 */
    getAsync(url: string, headers?: Record<string, string>): Promise<HttpResponse>;
    /** 标准异步 POST 请求 */
    postAsync(url: string, body?: string | Record<string, any>, headers?: Record<string, string>): Promise<HttpResponse>;
    /** 同步阻塞 GET 请求 (向后兼容旧版) */
    get(url: string, headers?: Record<string, string>): SyncHttpResponse;
    /** 同步阻塞 POST 请求 (向后兼容旧版) */
    post(url: string, body?: string | Record<string, any>, headers?: Record<string, string>): SyncHttpResponse;
  }

  /**
   * Multi-Toolbox 全局宿主注入接口
   */
  export interface HostToolbox {
    /** 当前宿主运行平台 */
    readonly platform: 'windows' | 'android' | 'other';
    /** 宿主 Bridge 规范版本 */
    readonly version: string;
    /** 宿主当前环境变量快照 */
    readonly env: HostEnvironment;

    /** 向宿主实时控制台输出普通日志 */
    log(...args: any[]): void;
    /** 向宿主实时控制台输出错误日志 (高亮红色标出) */
    error(...args: any[]): void;
    /** 更新当前任务的处理进度与状态文本 */
    setProgress(pct: number, status?: string): void;

    /** 文件系统操作模块 */
    readonly fs: FileSystemAPI;
    /** 插件专属持久化配置存储模块 */
    readonly storage: StorageAPI;
    /** 编解码工具模块 */
    readonly utils: UtilsAPI;
    /** 加密散列计算模块 */
    readonly crypto: CryptoAPI;
    /** 归档与解压缩模块 */
    readonly archive: ArchiveAPI;
    /** 原生图像处理流水线模块 */
    readonly image: ImageAPI;
    /** WebAssembly 沙箱算力模块 */
    readonly wasm: WasmAPI;
    /** 网络请求模块 */
    readonly http: HttpAPI;
  }
}

/**
 * 宿主全局注入的 Toolbox 核心对象
 */
declare const Toolbox: ToolboxAPI.HostToolbox;

/**
 * 现代标准异步 Fetch API (与 Toolbox.http.fetch 统一，非阻塞异步调度)
 */
declare function fetch(url: string, options?: ToolboxAPI.HttpRequestOptions): Promise<ToolboxAPI.HttpResponse>;
