
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import email.utils
from xml.etree.ElementTree import Element, SubElement, ElementTree

BASE_URL = "https://www.atelierfilz.com"
RESIDENTIAL_URL = f"{BASE_URL}/design-residentiel"
COMMERCIAL_URL = f"{BASE_URL}/design-commercial"

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
    res = requests.get(url, timeout=20)
    if res.status_code == 404:
        return "", None
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # Description
    texte = ""
    for tb in soup.select("div.sqs-block-content"):
        p_text = tb.get_text(separator=" ", strip=True)
        if p_text:
            texte = p_text.replace("Crédit photo", "").strip()
            break
    if len(texte) > MAX_DESCRIPTION_LENGTH:
        texte = texte[:MAX_DESCRIPTION_LENGTH].rsplit(" ", 1)[0] + "…"

    # Meilleure image (dans un bloc image)
    img_url = None
    image_blocks = soup.select("div.sqs-block-image img")
    for img_tag in image_blocks:
        src = img_tag.get("src")
        if src and src.startswith("http"):
            img_url = src
            break
        elif src and src.startswith("/"):
            img_url = urljoin(BASE_URL, src)
            break

    return texte, img_url

def build_rss(projects, file_name, flux_title, index_url):
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = flux_title
    SubElement(channel, "link").text = index_url
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
    tree.write(file_name, encoding="utf-8", xml_declaration=True)
    print(f"Flux RSS généré : {file_name}")

if __name__ == "__main__":
    projets_residentiels = get_projects(RESIDENTIAL_URL)
    projets_commerciaux = get_projects(COMMERCIAL_URL)
    build_rss(projets_residentiels, "atelier_filz_projets_residentiel.xml", "Atelier Filz – Projets Résidentiels", RESIDENTIAL_URL)
    build_rss(projets_commerciaux, "atelier_filz_projets_commercial.xml", "Atelier Filz – Projets Commerciaux", COMMERCIAL_URL)
