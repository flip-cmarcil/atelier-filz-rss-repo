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
MAX_IMAGES_PER_PROJECT = 4  # 3 à 4 photos, on limite à 4

def guess_mime_type(url: str) -> str:
    lower = url.split("?", 1)[0].lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    # défaut
    return "image/jpeg"

def first_non_empty(*vals):
    for v in vals:
        if v:
            v = v.strip()
            if v:
                return v
    return None

def url_from_img_tag(img_tag, base=BASE_URL):
    """
    Renvoie une URL absolue à partir d'un <img>, en essayant dans l'ordre:
    src, data-src, data-image, premier URL de srcset.
    """
    if not img_tag:
        return None

    # ordre de priorité
    src = first_non_empty(
        img_tag.get("src"),
        img_tag.get("data-src"),
        img_tag.get("data-image")
    )

    if not src:
        # essayer srcset (prendre le premier URL)
        srcset = img_tag.get("srcset")
        if srcset:
            # format: "https://... 300w, https://... 600w"
            first = srcset.split(",")[0].strip().split(" ")[0].strip()
            src = first or None

    if not src:
        return None

    return urljoin(base, src) if src.startswith("/") else src

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
    """
    Retourne (texte, [img_urls])
    """
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
    except Exception as e:
        print(f"Erreur chargement {url}: {e}")
        return "", []

    soup = BeautifulSoup(res.text, "html.parser")

    # Texte : première description
    texte = ""
    for tb in soup.select("div.sqs-html-content"):
        p = tb.find("p")
        if p and p.get_text(strip=True):
            texte = p.get_text(strip=True).replace("Crédit photo", "").strip()
            break
    if len(texte) > MAX_DESCRIPTION_LENGTH:
        texte = texte[:MAX_DESCRIPTION_LENGTH].rsplit(" ", 1)[0] + "…"

    # Images : récupérer plusieurs images du projet
    img_urls = []
    for img_tag in soup.select("div.sqs-block-image img"):
        img_url = url_from_img_tag(img_tag)
        if not img_url:
            continue
        # normaliser en absolu
        if img_url.startswith("/"):
            img_url = urljoin(BASE_URL, img_url)
        # enlever paramètres superflus si besoin ? (on garde tel quel pour Squarespace)
        # éviter doublons
        if img_url not in img_urls:
            img_urls.append(img_url)
        if len(img_urls) >= MAX_IMAGES_PER_PROJECT:
            break

    return texte, img_urls

def build_rss(projects, filename, category_name):
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"Atelier Filz – Projets {category_name.capitalize()}"
    SubElement(channel, "link").text = CATEGORIES[category_name]
    SubElement(channel, "description").text = f"Flux des projets {category_name} Atelier Filz"

    for title, href in projects:
        description, img_urls = get_project_details(href)

        if not img_urls:
            # Aucun visuel détecté : publier quand même un item sans enclosure
            item = SubElement(channel, "item")
            SubElement(item, "title").text = title
            SubElement(item, "link").text = href
            SubElement(item, "guid", {"isPermaLink": "true"}).text = href
            SubElement(item, "pubDate").text = email.utils.formatdate(usegmt=True)
            SubElement(item, "description").text = description
            continue

        # 1) Item principal (image #1) — identique à avant pour ne rien casser
        first_img = img_urls[0]
        item = SubElement(channel, "item")
        SubElement(item, "title").text = title
        SubElement(item, "link").text = href
        SubElement(item, "guid", {"isPermaLink": "true"}).text = href  # garde le même GUID principal
        SubElement(item, "pubDate").text = email.utils.formatdate(usegmt=True)
        SubElement(item, "description").text = description
        SubElement(item, "enclosure", {"url": first_img, "type": guess_mime_type(first_img)})

        # 2) Items supplémentaires (image #2 à #4) — un item par image
        total = min(len(img_urls), MAX_IMAGES_PER_PROJECT)
        for idx in range(1, total):
            img_url = img_urls[idx]
            itemn = SubElement(channel, "item")
            # suffixe pour distinguer les pins
            SubElement(itemn, "title").text = f"{title} ({idx+1}/{total})"
            SubElement(itemn, "link").text = href
            # GUID dérivé pour rester unique mais rattaché à la même page
            SubElement(itemn, "guid", {"isPermaLink": "false"}).text = f"{href}#image-{idx+1}"
            SubElement(itemn, "pubDate").text = email.utils.formatdate(usegmt=True)
            SubElement(itemn, "description").text = description
            SubElement(itemn, "enclosure", {"url": img_url, "type": guess_mime_type(img_url)})

    os.makedirs("public", exist_ok=True)
    with open(f"public/{filename}", "wb") as f:
        tree = ElementTree(rss)
        tree.write(f, encoding="utf-8", xml_declaration=True)
    print(f"RSS généré: public/{filename}")

if __name__ == "__main__":
    for category, url in CATEGORIES.items():
        projets = get_projects(url)
        build_rss(projets, f"atelier_filz_projets_{category}.xml", category)
