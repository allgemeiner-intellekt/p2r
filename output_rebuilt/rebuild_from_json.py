#!/usr/bin/env python3
"""
从 MinerU 的 content_list.json 重建 Markdown 和 HTML 文件。

核心理念：
- 按 JSON 中的顺序重建文档，脚注自然出现在每页末尾
- 保留所有有价值的信息，跳过页码等无用元素
- 生成干净、可读的输出
"""

import html
import json
from pathlib import Path
from typing import Optional


def load_content_list(json_path: Path) -> list:
    """加载 content_list.json"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def rebuild_markdown(
    content_list: list,
    images_dir: str = "images",
    include_page_markers: bool = True,
    include_footnotes: bool = True,
    include_aside: bool = False,
) -> str:
    """
    从 content_list 重建 Markdown 文档。

    Args:
        content_list: MinerU 输出的内容列表
        images_dir: 图片目录的相对路径
        include_page_markers: 是否插入页面分隔标记
        include_footnotes: 是否包含脚注
        include_aside: 是否包含边注（如 arXiv 标识）

    Returns:
        重建的 Markdown 字符串
    """
    lines = []
    current_page = -1

    for item in content_list:
        page_idx = item.get("page_idx", 0)
        item_type = item["type"]

        # 页面分隔标记
        if include_page_markers and page_idx != current_page:
            current_page = page_idx
            if current_page > 0:  # 第一页之前不加分隔
                lines.append(f"\n---\n<!-- Page {current_page + 1} -->\n")

        # 处理不同类型的元素
        if item_type == "text":
            text = item.get("text", "")
            level = item.get("text_level")

            if level == 1:
                # 一级标题
                lines.append(f"# {text}")
            elif level == 2:
                lines.append(f"## {text}")
            elif level == 3:
                lines.append(f"### {text}")
            else:
                # 普通段落
                lines.append(text)

        elif item_type == "page_footnote":
            if include_footnotes:
                text = item.get("text", "")
                # 用斜体表示脚注，保持视觉区分
                lines.append(f"*{text}*")

        elif item_type == "image":
            img_path = item.get("img_path", "")
            captions = item.get("image_caption", [])
            caption = captions[0] if captions else ""

            # 图片
            lines.append(f"![{caption}]({img_path})")

            # 图片标题（如果有）
            if caption:
                lines.append(f"*{caption}*")

        elif item_type == "table":
            table_body = item.get("table_body", "")
            captions = item.get("table_caption", [])
            caption = captions[0] if captions else ""

            # 表格标题（放在表格前面）
            if caption:
                lines.append(f"**{caption}**")

            # 表格内容（MinerU 输出的是 HTML 格式，Markdown 支持内嵌 HTML）
            lines.append(table_body)

        elif item_type == "list":
            list_items = item.get("list_items", [])
            for li in list_items:
                lines.append(li)

        elif item_type == "aside_text":
            if include_aside:
                text = item.get("text", "")
                lines.append(f"> {text}")

        elif item_type == "page_number":
            # 跳过页码
            pass

        else:
            # 未知类型，保留原始文本（如果有）
            if "text" in item:
                lines.append(item["text"])

    return "\n\n".join(lines)


def rebuild_html(
    content_list: list,
    images_dir: str = "images",
    title: str = "Document",
    include_page_markers: bool = True,
    include_footnotes: bool = True,
    include_aside: bool = False,
) -> str:
    """
    从 content_list 重建 HTML 文档。

    Args:
        content_list: MinerU 输出的内容列表
        images_dir: 图片目录的相对路径
        title: 文档标题
        include_page_markers: 是否插入页面分隔标记
        include_footnotes: 是否包含脚注
        include_aside: 是否包含边注

    Returns:
        重建的 HTML 字符串
    """

    # HTML 头部和样式
    html_parts = [
        f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        :root {{
            --text-color: #1a1a1a;
            --bg-color: #fdfdfd;
            --footnote-color: #555;
            --border-color: #ddd;
            --page-marker-color: #999;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.7;
            color: var(--text-color);
            background-color: var(--bg-color);
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        h1 {{ font-size: 1.8em; margin-top: 1.5em; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.4em; margin-top: 1.3em; }}
        h3 {{ font-size: 1.2em; margin-top: 1.2em; }}

        p {{ margin: 1em 0; }}

        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1.5em auto;
        }}

        .image-caption {{
            text-align: center;
            font-style: italic;
            color: #666;
            margin-top: -1em;
            margin-bottom: 1.5em;
            font-size: 0.9em;
        }}

        .footnote {{
            color: var(--footnote-color);
            font-size: 0.9em;
            padding: 0.5em 1em;
            margin: 0.5em 0;
            border-left: 3px solid var(--border-color);
            background-color: #f9f9f9;
        }}

        .page-marker {{
            color: var(--page-marker-color);
            font-size: 0.8em;
            text-align: center;
            margin: 2em 0;
            padding: 0.5em;
            border-top: 1px dashed var(--border-color);
        }}

        .aside {{
            color: #888;
            font-size: 0.85em;
            font-style: italic;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1.5em 0;
            font-size: 0.9em;
        }}

        table th, table td {{
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            text-align: left;
        }}

        table th {{
            background-color: #f5f5f5;
            font-weight: bold;
        }}

        table tr:nth-child(even) {{
            background-color: #fafafa;
        }}

        .table-caption {{
            font-weight: bold;
            margin-bottom: 0.5em;
        }}

        ul, ol {{
            margin: 1em 0;
            padding-left: 2em;
        }}

        li {{
            margin: 0.5em 0;
        }}
    </style>
</head>
<body>
"""
    ]

    current_page = -1

    for item in content_list:
        page_idx = item.get("page_idx", 0)
        item_type = item["type"]

        # 页面分隔标记
        if include_page_markers and page_idx != current_page:
            current_page = page_idx
            if current_page > 0:
                html_parts.append(f'<div class="page-marker">Page {current_page + 1}</div>')

        # 处理不同类型的元素
        if item_type == "text":
            text = html.escape(item.get("text", ""))
            level = item.get("text_level")

            if level == 1:
                html_parts.append(f"<h1>{text}</h1>")
            elif level == 2:
                html_parts.append(f"<h2>{text}</h2>")
            elif level == 3:
                html_parts.append(f"<h3>{text}</h3>")
            else:
                html_parts.append(f"<p>{text}</p>")

        elif item_type == "page_footnote":
            if include_footnotes:
                text = html.escape(item.get("text", ""))
                html_parts.append(f'<div class="footnote">{text}</div>')

        elif item_type == "image":
            img_path = html.escape(item.get("img_path", ""))
            captions = item.get("image_caption", [])
            caption = html.escape(captions[0]) if captions else ""

            html_parts.append(f'<img src="{img_path}" alt="{caption}">')
            if caption:
                html_parts.append(f'<p class="image-caption">{caption}</p>')

        elif item_type == "table":
            table_body = item.get("table_body", "")  # 已经是 HTML，不需要 escape
            captions = item.get("table_caption", [])
            caption = html.escape(captions[0]) if captions else ""

            if caption:
                html_parts.append(f'<p class="table-caption">{caption}</p>')
            html_parts.append(table_body)

        elif item_type == "list":
            list_items = item.get("list_items", [])
            html_parts.append("<ul>")
            for li in list_items:
                # 移除 Markdown 列表标记
                li_text = li.lstrip("- ")
                html_parts.append(f"<li>{html.escape(li_text)}</li>")
            html_parts.append("</ul>")

        elif item_type == "aside_text":
            if include_aside:
                text = html.escape(item.get("text", ""))
                html_parts.append(f'<p class="aside">{text}</p>')

        elif item_type == "page_number":
            pass  # 跳过页码

    # HTML 尾部
    html_parts.append("""
</body>
</html>
""")

    return "\n".join(html_parts)


def main():
    """主函数：处理示例文件"""

    # 路径配置
    input_dir = Path("/Users/yuhanli/allgemeiner-intellekt/p2r/output")
    output_dir = Path("/Users/yuhanli/allgemeiner-intellekt/p2r/output_rebuilt")

    # 查找 content_list.json
    raw_dir = input_dir / "raw"
    json_files = list(raw_dir.glob("*_content_list.json"))

    if not json_files:
        print("Error: No content_list.json found")
        return

    json_path = json_files[0]
    print(f"Processing: {json_path.name}")

    # 加载内容
    content_list = load_content_list(json_path)
    print(f"Loaded {len(content_list)} elements")

    # 统计
    from collections import Counter

    types = Counter(item["type"] for item in content_list)
    print(f"Element types: {dict(types)}")

    # 复制 images 目录
    import shutil

    src_images = input_dir / "images"
    dst_images = output_dir / "images"
    if src_images.exists():
        if dst_images.exists():
            shutil.rmtree(dst_images)
        shutil.copytree(src_images, dst_images)
        print(f"Copied images directory")

    # 重建 Markdown
    md_content = rebuild_markdown(
        content_list,
        include_page_markers=True,
        include_footnotes=True,
        include_aside=False,
    )

    md_path = output_dir / "rebuilt.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Generated: {md_path}")

    # 重建 HTML
    html_content = rebuild_html(
        content_list,
        title="MinerU: An Open-Source Solution for Precise Document Content Extraction",
        include_page_markers=True,
        include_footnotes=True,
        include_aside=False,
    )

    html_path = output_dir / "rebuilt.html"
    html_path.write_text(html_content, encoding="utf-8")
    print(f"Generated: {html_path}")

    # 对比：生成一个不含脚注的版本（模拟 MinerU 默认行为）
    md_no_footnotes = rebuild_markdown(
        content_list,
        include_page_markers=False,
        include_footnotes=False,
        include_aside=False,
    )

    md_no_fn_path = output_dir / "rebuilt_no_footnotes.md"
    md_no_fn_path.write_text(md_no_footnotes, encoding="utf-8")
    print(f"Generated (no footnotes): {md_no_fn_path}")

    # 统计脚注
    footnotes = [item for item in content_list if item["type"] == "page_footnote"]
    print(f"\n=== Footnotes ({len(footnotes)}) ===")
    for fn in footnotes:
        print(f"  Page {fn['page_idx'] + 1}: {fn['text'][:60]}...")


if __name__ == "__main__":
    main()
