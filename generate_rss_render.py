import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import email.utils
from xml.etree.ElementTree import Element, SubElement, ElementTree
import shutil
import os

BASE_URL = "https://www.atelierfilz.com"
INDEX_URL = f"{BASE_URL}/projets"

MAX_DESCRIPTION_LENGTH = 300  # longueur maximale du résumé pour Pinterest
RSS_FILE = "atelier_filz_projets_rss.xml"

def get_projects():
    res = requests.get(INDEX_URL, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    projects = []
    for a in soup.select("div.sqs-html-content h4 a[href]"):
        title = a.get_text(strip=True) or "Projet Atelier Filz"
        href = urljoin(BASE_URL, a["href"])
        projects.append((title, href))
    return projects

def get_project_details(url):
    res = requests.get(url, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # Texte : premier bloc non vide
    texte = ""
    for tb in soup.select("div.sqs-block-content"):
        p_text = tb.get_text(separator="\n", strip=True)
        if p_text:
            texte = p_text.replace("Crédit photo", "").strip()
            break
    if len(texte) > MAX_DESCRIPTION_LENGTH:
        texte = texte[:MAX_DESCRIPTION_LENGTH].rsplit(" ", 1)[0] + "…"

    # Image : première image pertinente (dans sqs-block-image)
    img_url = None
    img_tag = soup.select_one("div.sqs-block-image img")
    if img_tag and img_tag.get("src"):
        src = img_tag["src"]
        img_url = urljoin(BASE_URL, src) if src.startswith("/") else src

    return texte, img_url

def build_rss(projects):
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = "Atelier Filz – Projets"
    SubElement(channel, "link").text = INDEX_URL
    SubElement(channel, "description").text = "Flux automatique des réalisations Atelier Filz"

    for title, href in projects:
        description, img_url = get_project_details(href)
        item = SubElement(channel, "item")
        SubElement(item, "title").text = title
        SubElement(item, "link").text = href
        SubElement(item, "guid", {"isPermaLink": "true"}).text = href
        SubElement(item, "pubDate").text = email.utils.formatdate(usegmt=True)
        SubElement(item, "description").text = description
        if img_url:
            SubElement(item, "enclosure", {"url": img_url, "type": "image/jpeg"})

    tree = ElementTree(rss)
    tree.write(RSS_FILE, encoding="utf-8", xml_declaration=True)

    # Déplacement vers le dossier public_html
    public_html_path = os.path.expanduser("~/public_html/")
    target_path = os.path.join(public_html_path, RSS_FILE)
    try:
        shutil.copy(RSS_FILE, target_path)
        print(f"RSS déplacé dans public_html : {target_path}")
    except Exception as e:
        print(f"Erreur lors du déplacement : {e}")

if __name__ == "__main__":
    projets = get_projects()
    build_rss(projets)
