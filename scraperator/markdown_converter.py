from typing import Optional, Dict, Any, List, Union, Tuple, Set
from bs4 import BeautifulSoup, Tag, NavigableString
import re


class MarkdownConverter:
    def __init__(
            self,
            strip_tags: Optional[List[str]] = None,
            keep_tags: Optional[List[str]] = None,
            content_selectors: Optional[List[str]] = None,
            preserve_images: bool = True,
            preserve_links: bool = True,
            preserve_tables: bool = True,
            include_title: bool = True,
            compact_output: bool = False
    ):
        self.strip_tags = strip_tags or ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]
        self.keep_tags = keep_tags or ["article", "main", "div", "section", "p", "h1", "h2", "h3", "h4", "h5", "h6"]
        self.content_selectors = content_selectors or [
                "article", "main", ".content", "#content", ".post-content",
                ".article-content", ".entry-content", "[role='main']"
        ]
        self.preserve_images = preserve_images
        self.preserve_links = preserve_links
        self.preserve_tables = preserve_tables
        self.include_title = include_title
        self.compact_output = compact_output

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title_tag = soup.title
        if title_tag:
            return title_tag.string.strip()
        h1_tag = soup.find("h1")
        if h1_tag:
            return h1_tag.get_text().strip()
        return ""

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text

    def _handle_heading(self, tag: Tag, level: int) -> str:
        text = tag.get_text().strip()
        return f"{'#' * level} {text}\n\n"

    def _handle_paragraph(self, tag: Tag) -> str:
        text = tag.get_text().strip()
        if not text:
            return ""
        return f"{text}\n\n"

    def _handle_list(self, tag: Tag, ordered: bool = False) -> str:
        result = []
        for i, item in enumerate(tag.find_all("li", recursive=False)):
            prefix = f"{i + 1}. " if ordered else "* "
            text = item.get_text().strip()
            result.append(f"{prefix}{text}")
        return "\n".join(result) + "\n\n"

    def _handle_link(self, tag: Tag) -> str:
        if not self.preserve_links:
            return tag.get_text().strip()

        text = tag.get_text().strip()
        href = tag.get("href", "")
        title = tag.get("title", "")

        if not href or not text:
            return text

        if title:
            return f"[{text}]({href} \"{title}\")"
        return f"[{text}]({href})"

    def _handle_image(self, tag: Tag) -> str:
        if not self.preserve_images:
            return ""

        alt = tag.get("alt", "")
        src = tag.get("src", "")
        title = tag.get("title", "")

        if not src:
            return ""

        if src.startswith("/"):
            parent_link = tag.find_parent("a")
            if parent_link and parent_link.get("href"):
                href = parent_link.get("href", "")
                if href.startswith("http"):
                    base = href.split("//")[0] + "//" + href.split("//")[1].split("/")[0]
                    src = base + src

        if title:
            return f"![{alt}]({src} \"{title}\")"
        return f"![{alt}]({src})"

    def _handle_table(self, tag: Tag) -> str:
        if not self.preserve_tables:
            return tag.get_text().strip() + "\n\n"

        result = []

        headers = []
        header_row = tag.find("thead")
        if header_row:
            for th in header_row.find_all("th"):
                headers.append(th.get_text().strip())

        if not headers and tag.find("tr"):
            first_row = tag.find("tr")
            for cell in first_row.find_all(["th", "td"]):
                headers.append(cell.get_text().strip())

        if not headers:
            first_row = tag.find("tr")
            if first_row:
                cell_count = len(first_row.find_all(["td", "th"]))
                headers = [f"Column {i + 1}" for i in range(cell_count)]
            else:
                return tag.get_text().strip() + "\n\n"

        result.append("| " + " | ".join(headers) + " |")
        result.append("| " + " | ".join(["---"] * len(headers)) + " |")

        body = tag.find("tbody") or tag
        for row in body.find_all("tr"):
            if not header_row and row == tag.find("tr"):
                continue

            cells = []
            row_cells = row.find_all(["td", "th"])

            for cell in row_cells:
                content = cell.get_text().strip()
                colspan = int(cell.get("colspan", 1))
                if colspan > 1:
                    cells.extend([content] + [""] * (colspan - 1))
                else:
                    cells.append(content)

            while len(cells) < len(headers):
                cells.append("")

            cells = cells[:len(headers)]

            if cells:
                result.append("| " + " | ".join(cells) + " |")

        return "\n".join(result) + "\n\n"

    def _handle_blockquote(self, tag: Tag) -> str:
        lines = tag.get_text().strip().split("\n")
        result = []
        for line in lines:
            result.append(f"> {line}")
        return "\n".join(result) + "\n\n"

    def _handle_code(self, tag: Tag) -> str:
        language = tag.get("class", [""])[0].replace("language-", "") if tag.get("class") else ""
        code = tag.get_text()
        if language:
            return f"```{language}\n{code}\n```\n\n"
        return f"```\n{code}\n```\n\n"

    def _handle_inline_code(self, tag: Tag) -> str:
        return f"`{tag.get_text()}`"

    def _handle_strong(self, tag: Tag) -> str:
        return f"**{tag.get_text()}**"

    def _handle_em(self, tag: Tag) -> str:
        return f"*{tag.get_text()}*"

    def _handle_hr(self, tag: Tag) -> str:
        return "---\n\n"

    def _process_node(self, node: Union[Tag, NavigableString]) -> str:
        if isinstance(node, NavigableString):
            return str(node)

        tag_name = node.name

        if tag_name in self.strip_tags:
            return ""

        handlers = {
                "h1"        : lambda t: self._handle_heading(t, 1),
                "h2"        : lambda t: self._handle_heading(t, 2),
                "h3"        : lambda t: self._handle_heading(t, 3),
                "h4"        : lambda t: self._handle_heading(t, 4),
                "h5"        : lambda t: self._handle_heading(t, 5),
                "h6"        : lambda t: self._handle_heading(t, 6),
                "p"         : self._handle_paragraph,
                "ul"        : lambda t: self._handle_list(t, ordered=False),
                "ol"        : lambda t: self._handle_list(t, ordered=True),
                "a"         : self._handle_link,
                "img"       : self._handle_image,
                "table"     : self._handle_table,
                "blockquote": self._handle_blockquote,
                "pre"       : self._handle_code,
                "code"      : self._handle_inline_code,
                "strong"    : self._handle_strong,
                "b"         : self._handle_strong,
                "em"        : self._handle_em,
                "i"         : self._handle_em,
                "hr"        : self._handle_hr,
        }

        if tag_name in handlers:
            return handlers[tag_name](node)

        result = ""
        for child in node.children:
            result += self._process_node(child)

        return result

    def _find_content_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        for selector in self.content_selectors:
            if selector.startswith("."):
                containers = soup.find_all(class_=selector[1:])
            elif selector.startswith("#"):
                container = soup.find(id=selector[1:])
                containers = [container] if container else []
            elif "[" in selector and "]" in selector:
                attr_name = selector.split("[")[1].split("=")[0]
                attr_value = selector.split("=")[1].split("]")[0].strip("'\"")
                containers = soup.find_all(attrs={attr_name: attr_value})
            else:
                containers = soup.find_all(selector)

            if containers:
                if len(containers) == 1:
                    return containers[0]

                containers_with_length = [(c, len(c.get_text())) for c in containers]
                containers_with_length.sort(key=lambda x: x[1], reverse=True)
                return containers_with_length[0][0]

        for tag_name in self.keep_tags:
            tags = soup.find_all(tag_name)

            if tags:
                tags_with_length = [(tag, len(tag.get_text())) for tag in tags]
                tags_with_length.sort(key=lambda x: x[1], reverse=True)
                return tags_with_length[0][0]

        return soup.body

    def convert(self, html: str) -> str:
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        for tag_name in self.strip_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        content = self._find_content_container(soup)
        if not content:
            content = soup

        title = self._extract_title(soup) if self.include_title else ""
        result = f"# {title}\n\n" if title else ""

        markdown = result + self._process_node(content)

        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        if self.compact_output:
            markdown = re.sub(r'\n\n+', '\n\n', markdown)

        return markdown.strip()