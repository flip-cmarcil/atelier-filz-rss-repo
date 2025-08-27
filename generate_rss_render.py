import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import email.utils
from xml.etree.ElementTree import Element, SubElement, ElementTree

BASE_URL = "https://www.atelierfilz.com"
CATEGORIES = {
    "residentiel": f"{BASE_URL}/design-residentiel",
    "commercial": f"{BASE_URL}/design-commercial"
}
MAX_DESCRIPTION_LENGTH = 300

def get_projects(index_url):
    res = requests.get(index_url, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    projects = []
    for a in soup.select("div.sqs-html-content h4 a[href]"):
        title = a.get_text(strip=True) or "Projet Atelier Filz"
        href = urljoin(BASE_URL, a["href"])
        projects.append((title, href))
    return projects

def get_project_details(url):
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
    except Exception as e:
        print(f"Erreur chargement {url}: {e}")
        return "", None

    soup = BeautifulSoup(res.text, "html.parser")

    # Description : premier paragraphe
    texte = ""
    for tb in soup.select("div.sqs-html-content"):
        p = tb.find("p")
        if p and p.get_text(strip=True):
            texte = p.get_text(strip=True).replace("Crédit photo", "").strip()
            break
    if len(texte) > MAX_DESCRIPTION_LENGTH:
        texte = texte[:MAX_DESCRIPTION_LENGTH].rsplit(" ", 1)[0] + "…"

    # Image : première image visible dans la galerie
    img_url = None
    gallery_imgs = soup.select("img")
    for img in gallery_imgs:
        src = img.get("src")
        if src and "format=original" in src:
            img_url = urljoin(BASE_URL, src)
            break

    return texte, img_url

def build_rss(projects, filename, category_name):
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"Atelier Filz – Projets {category_name.capitalize()}"
    SubElement(channel, "link").text = CATEGORIES[category_name]
    SubElement(channel, "description").text = f"Flux des projets {category_name} Atelier Filz"

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

    os.makedirs("public", exist_ok=True)
    with open(f"public/{filename}", "wb") as f:
        tree = ElementTree(rss)
        tree.write(f, encoding="utf-8", xml_declaration=True)
    print(f"RSS généré: public/{filename}")

if __name__ == "__main__":
    for category, url in CATEGORIES.items():
        projets = get_projects(url)
        build_rss(projets, f"atelier_filz_projets_{category}.xml", category)
