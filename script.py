import os
import time
import json
import fitz  # PyMuPDF
import csv
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
# CONFIG
# ============================================================
BASE_URL = "https://unitn.coursecatalogue.cineca.it/cerca-insegnamenti"
SAVE_DIR = "unitn_data_specific"
os.makedirs(SAVE_DIR, exist_ok=True)

# ============================================================
# SETUP BROWSER
# ============================================================
def init_driver(download_dir):
    chrome_options = Options()
    #chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,  # don't open PDF in-browser
    }
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(40)
    return driver

# ============================================================
# PDF TEXT EXTRACTION
# ============================================================
def extract_between_texts(pdf_path, start_marker, end_marker):
    """Extracts text between two markers from PDF."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text")

    start_idx = full_text.find(start_marker)
    end_idx = full_text.find(end_marker, start_idx + len(start_marker))

    if start_idx != -1 and end_idx != -1:
        return full_text[start_idx + len(start_marker):end_idx].strip()
    elif start_idx != -1:
        return full_text[start_idx + len(start_marker):].strip()
    else:
        return None

# ============================================================
# WAIT UNTIL PDF DOWNLOADED
# ============================================================
def wait_for_pdf(download_dir, timeout=30):
    """Wait until a new PDF file appears in download directory."""
    before = set(os.listdir(download_dir))
    for _ in range(timeout * 2):
        time.sleep(0.5)
        after = set(os.listdir(download_dir))
        new_files = list(after - before)
        if any(f.lower().endswith(".pdf") for f in new_files):
            pdfs = [f for f in new_files if f.lower().endswith(".pdf")]
            return os.path.join(download_dir, pdfs[0])
    return None

# ============================================================
# SCRAPE ONE COURSE
# ============================================================
def scrape_course(driver, course):
    result = dict(course)
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(BASE_URL)
        time.sleep(3)
        link = driver.find_element(By.XPATH, "//a[contains(., 'EN')]")
        link.click()

        for year in range(2025, 2020, -1):

            driver.get(BASE_URL)

            # Step 2: Fill search box
            search_box = wait.until(EC.presence_of_element_located((By.NAME, "insegnamento")))
            search_box.clear()
            search_box.send_keys(course["Insegnamento - descrizione"])
            
            time.sleep(0.2)

            select = Select(driver.find_element(By.NAME, 'anno_off'))
            select.select_by_visible_text(f'{year}/{year + 1}')

            print(f'selecting year {year}/{year + 1}')
            
            time.sleep(0.2)

            # Step 3: Click "Esegui Ricerca"
            search_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Submit')]")))
            search_button.click()

            # Step 4: Wait for link with correct course code
            time.sleep(0.5)
            try:
                link = wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        f"//a[contains(@href, 'insegnamenti') and contains(., '{course['Insegnamento - codice']}')]"
                    ))
                )
                result['course_page_url'] = link.get_attribute("href")
                link.click()
            except Exception as e:
                print(f"\nERROR: Could not find link for course {course['Insegnamento - codice']} - {course['Insegnamento - descrizione']} for year {year}")
                continue

            # Step 5: Click the “Salva PDF” button (not a link!)
            pdf_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., ' Save PDF ')]"))
            )
            pdf_button.click()

            # Step 6: Wait for PDF to appear
            pdf_path = wait_for_pdf(SAVE_DIR)
            if not pdf_path:
                result["error"] = "PDF not downloaded"
                return result

            # Step 7: Extract text between markers
            result["pdf_path"] = pdf_path
            result["objectives"] = extract_between_texts(
                pdf_path,
                "Course objectives and learning outcomes",
                "Entrance requirement"
            )

            result["prerequisites"] = extract_between_texts(
                pdf_path,
                "Entrance requirement",
                "Contents",
            )

            result["assessment"] = extract_between_texts(
                pdf_path,
                "Test and assessment criteria",
                "Bibliography/Study materials",
            )

            result['year of data'] = f'{year}/{year + 1}'

            # Save intermediate JSON
            out_path = os.path.join(SAVE_DIR, f"{course['Insegnamento - codice']}_{course['Insegnamento - descrizione']}_{year}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            if result["objectives"] is not None:
                break  # Successfully got data, exit year loop
            else:
                print(f"Warning: 'Obiettivi' section not found for year {year}, trying previous year...")

    except Exception as e:
        result["error"] = str(e)
        print(e)

    return result

# ============================================================
# MAIN
# ============================================================
def main():
    # Load specific courses from specific.txt (case-insensitive). If file empty/missing, ignore.
    specific_courses = set()
    if os.path.exists("specific.txt"):
        with open("specific.txt", "r", encoding="utf-8") as f:
            specific_courses = set(line.strip().lower() for line in f if line.strip())

    with open("data.json", "r", encoding="utf-8") as f:
        courses = json.load(f)
        # If specific.txt contains names, filter courses (case-insensitive); otherwise ignore
        if specific_courses:
            original_count = len(courses)
            courses = [course for course in courses if course.get("Insegnamento - descrizione", "").lower() in specific_courses]
            print(f"Filtered courses: {len(courses)} of {original_count} from specific.txt")
        else:
            print("specific.txt is empty or missing — no filtering applied")
        driver = init_driver(SAVE_DIR)
        results = []
        courses_seen = set()


        for course in tqdm(courses, desc="Processing courses"):
            if course["Insegnamento - descrizione"] in courses_seen:
                print(f"Skipping duplicate course: {course['Insegnamento - descrizione']}")
                continue
            res = scrape_course(driver, course)
            results.append(res)
            courses_seen.add(course["Insegnamento - descrizione"])

        driver.quit()

        with open(os.path.join(SAVE_DIR, "all_results.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Also export results to CSV for easy analysis
        csv_path = os.path.join(SAVE_DIR, "all_results.csv")
        fieldnames = [
            "Insegnamento - codice",
            "Insegnamento - descrizione",
            "year of data",
            "course_page_url",
            "pdf_path",
            "objectives",
            "prerequisites",
            "assessment",
            "error",
        ]
        try:
            with open(csv_path, "w", encoding="utf-8", newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    row = {k: r.get(k, "") for k in fieldnames}
                    writer.writerow(row)
            print(f"CSV exported to: {csv_path}")
        except Exception as e:
            print(f"Failed to write CSV: {e}")
        print("\n✅ Done! Data and PDFs saved in:", SAVE_DIR)

# ============================================================
if __name__ == "__main__":
    main()
