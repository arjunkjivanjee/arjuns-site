import requests
import json
import os
from datetime import datetime

# Configuration
TEMPLATE_FILE = "article_template.html"
INDEX_FILE = "index.html"

def load_env_vars():
    """Simple .env loader to avoid external dependencies"""
    env_vars = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        # It's okay if .env doesn't exist, we might be on Netlify
        pass
    return env_vars

env = load_env_vars()
# Prioritize system environment variables (Netlify), fallback to .env file
NOTION_TOKEN = os.environ.get("NOTION_TOKEN") or env.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID") or env.get("DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    print("Error: Missing NOTION_TOKEN or DATABASE_ID. Set them in .env or as environment variables.")
    exit(1)

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def fetch_database_pages():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching database: {response.text}")
        return []
    return response.json().get("results", [])

def fetch_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching blocks: {response.text}")
        return []
    return response.json().get("results", [])

def render_block(block):
    btype = block["type"]
    if btype == "paragraph":
        text = "".join([t["plain_text"] for t in block["paragraph"]["rich_text"]])
        return f"<p>{text}</p>" if text else ""
    elif btype == "heading_1":
        text = "".join([t["plain_text"] for t in block["heading_1"]["rich_text"]])
        return f"<h1>{text}</h1>"
    elif btype == "heading_2":
        text = "".join([t["plain_text"] for t in block["heading_2"]["rich_text"]])
        return f"<h2>{text}</h2>"
    elif btype == "heading_3":
        text = "".join([t["plain_text"] for t in block["heading_3"]["rich_text"]])
        return f"<h3>{text}</h3>"
    elif btype == "bulleted_list_item":
        text = "".join([t["plain_text"] for t in block["bulleted_list_item"]["rich_text"]])
        return f"<li>{text}</li>"
    return ""

def format_date(date_str):
    if not date_str:
        return ""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d.%m.%Y")
    except ValueError:
        return date_str

def generate_article_html(title, date, topic, content):
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()
    
    html = template.replace("{{ title }}", title)
    html = html.replace("{{ date }}", date)
    html = html.replace("{{ topic }}", topic)
    html = html.replace("{{ content }}", content)
    
    return html

def generate_list_item_html(title, date, topics, filename):
    # Generate HTML for each topic tag
    tags_html = ""
    for topic in topics:
        tags_html += f"""
        <div class="article-tag-container">
          <p class="article-tag"><span class="text-rgb-30-30-30">{topic}</span></p>
        </div>
        """
    
    return f"""
      <a href="{filename}" class="article-row">
        <div class="article-date-container">
          <div class="article-margin">
            <div class="article-dot"></div>
          </div>
          <div class="article-date-wrapper">
            <p class="article-date"><span class="text-rgb-30-30-30">{date}</span></p>
          </div>
        </div>
        <div class="article-title-container">
          <div class="article-title-wrapper">
            <p class="article-title"><span class="text-rgb-30-30-30">{title}</span></p>
          </div>
        </div>
        <div class="article-tags-wrapper" style="display: flex; gap: 4px; width: 50px; justify-content: flex-end;">
          {tags_html}
        </div>
        <div class="article-arrow">
          <img src="images/article-vector-29.svg" class="article-vector-bg" alt="vector" />
          <img src="images/article-vector-30.svg" class="article-vector-fg" alt="vector" />
        </div>
      </a>
    """

def main():
    print("Fetching articles from Notion...")
    pages = fetch_database_pages()
    
    articles_html_list = []
    article_count = 0
    
    for page in pages:
        props = page["properties"]
        
        # Extract properties
        title_prop = props.get("Name", {}).get("title", [])
        title = "".join([t["plain_text"] for t in title_prop]) if title_prop else "Untitled"
        
        date_prop = props.get("Date", {}).get("date", {})
        date_raw = date_prop.get("start") if date_prop else None
        date_formatted = format_date(date_raw) if date_raw else ""
        
        type_prop = props.get("Type", {}).get("multi_select", [])
        topics = [t["name"] for t in type_prop] if type_prop else ["General"]
        topic_str = ", ".join(topics) # For the article page header
        
        # Generate filename
        filename = f"article-{page['id']}.html"
        
        # Fetch content
        print(f"Processing: {title}")
        blocks = fetch_page_blocks(page["id"])
        content_html = "\n".join([render_block(b) for b in blocks])
        
        # Generate Article Page
        full_html = generate_article_html(title, date_formatted, topic_str, content_html)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_html)
            
        # Generate List Item (pass list of topics)
        articles_html_list.append(generate_list_item_html(title, date_formatted, topics, filename))
        article_count += 1
        
    # Update index.html
    print("Updating index.html...")
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        index_content = f.read()
        
    # Inject article list
    start_marker = "<!-- ARTICLES_START -->"
    end_marker = "<!-- ARTICLES_END -->"
    
    if start_marker in index_content and end_marker in index_content:
        pre = index_content.split(start_marker)[0]
        post = index_content.split(end_marker)[1]
        new_list_html = "\n".join(articles_html_list)
        updated_content = pre + start_marker + "\n" + new_list_html + "\n" + end_marker + post
        
        # Update count
        # Regex or simple replace for the count (4) -> (N)
        # We know the current format is <p class="text-104"><span class="text-rgb-30-30-30">(4)</span></p>
        # Let's find the class and replace the number inside
        import re
        updated_content = re.sub(r'<p class="text-104"><span class="text-rgb-30-30-30">\(\d+\)</span></p>', 
                                 f'<p class="text-104"><span class="text-rgb-30-30-30">({article_count})</span></p>', 
                                 updated_content)
        
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print("Site updated successfully!")
    else:
        print("Error: Markers not found in index.html")

if __name__ == "__main__":
    main()
