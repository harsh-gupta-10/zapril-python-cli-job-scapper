import os
import json
import hashlib
import time
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.progress import track
from dotenv import load_dotenv

from openai import OpenAI
import google.generativeai as genai

console = Console()

class DescriptionImprover:
    """
    Uses AI to clean job descriptions, extract skills, and generate key takeaways.
    Now using Hackclub API (OpenAI-compatible) for processing.
    Results are cached locally to avoid redundant API calls and save costs.
    """
    def __init__(self, cache_dir: str = "cache"):
        load_dotenv()
        # Load global settings
        self.ai_processing_enabled = True
        try:
            settings_path = Path(__file__).parent.parent / "settings.json"
            if settings_path.exists():
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    self.ai_processing_enabled = settings.get("ai_processing_enabled", True)
        except Exception as e:
            console.print(f"[dim yellow]Warning: Could not load settings for AI toggle: {e}[/]")

        # Prefer Hackclub API as requested by user
        self.api_key = os.getenv("Hackclub-API")
        self.enabled = bool(self.api_key) and self.ai_processing_enabled
        
        if self.enabled:
            # Hackclub API is OpenAI-compatible
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://ai.hackclub.com/proxy/v1"
            )
            # Using gpt-4o-mini for high speed and reliable output
            self.model = "gpt-4o-mini"
            
        # Fallback to Google Gemini if available
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if self.google_api_key and self.ai_processing_enabled:
            genai.configure(api_key=self.google_api_key)
            # Using gemini-flash-latest as it's often more stable across regions
            self.gemini_model = genai.GenerativeModel("gemini-flash-latest")
            self.google_enabled = True
        else:
            self.google_enabled = False
            
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "description_cache.json"
        
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            console.print(f"[dim yellow]Warning: Could not save description cache: {e}[/]")

    def _get_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest()

    def improve_description(self, description: str) -> dict:
        """Calls AI API to improve description and extract skills."""
        if not description or not str(description).strip():
            return {"skills": [], "key_takeaways": [], "cleaned_description": ""}
        
        desc_str = str(description).strip()
        text_hash = self._get_hash(desc_str)
        
        if text_hash in self.cache:
            cached = self.cache[text_hash]
            # If it has salary and it's not 'Not specified' and has skills, we're good
            if (cached.get("salary_expectation") and cached.get("salary_expectation") != "Not specified" 
                and cached.get("skills") and len(cached.get("skills")) > 0):
                return cached
            # Otherwise, we continue to re-process (the logic below will handle it)
            
        if not self.enabled and not self.google_enabled:
            return {"skills": [], "key_takeaways": [], "cleaned_description": desc_str, "salary_expectation": "Not specified"}
            
        prompt = f"""
You are an expert technical recruiter and copywriter specializing in the Indian and Global job markets.
I will give you a raw job description. Your goal is to extract structured data and clean it up.

Your task:
1. Extract a clean, bulleted list of the top technical and soft skills required. Maximum 10 skills.
2. Generate a 3-bullet summary (key takeaways) of the role.
3. Clean up the full job description into a standardized, easy-to-read Markdown format.
4. ESTIMATE THE SALARY RANGE. This is crucial. 
   - If the salary is mentioned (e.g. "5 - 8 LPA", "₹40,000 - ₹60,000 per month"), extract it.
   - If NOT mentioned, use your knowledge of the industry, company size (if provided), and job title to provide a realistic range for the location (e.g., "₹6L - ₹10L PA" for a mid-level dev in Mumbai).
   - Format: Use "₹X - ₹Y PA" for annual or "₹X - ₹Y PM" for monthly. Use "$" for international roles.
   - Be specific. Avoid "Competitive" or "As per industry standards".
   - If absolutely impossible to even guess, return "Not specified".

Return ONLY a valid JSON object:
{{
  "skills": ["Skill1", "Skill2"],
  "key_takeaways": ["Point 1", "Point 2", "Point 3"],
  "cleaned_description": "Markdown text here...",
  "salary_expectation": "Estimated Range"
}}

Raw Job Description:
---
{desc_str[:15000]}
---
"""
        try:
            # Re-processing logic is now handled above at the start of the method
            
            result = None
            
            # 1. Try Hackclub API (OpenAI)
            if self.enabled:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that returns only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    result_text = response.choices[0].message.content
                    result = json.loads(result_text)
                except Exception as e:
                    console.print(f"[dim red]Hackclub-API Error: {e}. Trying Gemini...[/]")
            
            # 2. Try Gemini Fallback if Hackclub failed or is disabled
            if result is None and self.google_enabled:
                try:
                    gen_response = self.gemini_model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    result = json.loads(gen_response.text)
                except Exception as e:
                    console.print(f"[dim red]Gemini API Error: {e}[/]")
            
            if result:
                cleaned_result = {
                    "skills": result.get("skills", []),
                    "key_takeaways": result.get("key_takeaways", []),
                    "cleaned_description": result.get("cleaned_description", desc_str),
                    "salary_expectation": result.get("salary_expectation", "Not specified")
                }
                self.cache[text_hash] = cleaned_result
                return cleaned_result

            return {"skills": [], "key_takeaways": [], "cleaned_description": desc_str, "salary_expectation": "Not specified"}

        except Exception as e:
            error_msg = str(e)
            console.print(f"[dim red]AI Processing Error: {error_msg}[/]")
            time.sleep(1)
            return {"skills": [], "key_takeaways": [], "cleaned_description": desc_str, "salary_expectation": "Not specified"}

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process an entire dataframe of jobs."""
        if df.empty:
            return df
            
        if not self.enabled:
            console.print("[yellow]⚠️ Hackclub-API key not found. Skipping AI Description Improvement.[/]")
            if "skills" not in df.columns:
                df["skills"] = "[]"
            if "key_takeaways" not in df.columns:
                df["key_takeaways"] = "[]"
            if "salary_expectation" not in df.columns:
                df["salary_expectation"] = "Not specified"
            return df
            
        console.print(f"[cyan]✨ Enhancing {len(df)} job descriptions using AI (Hackclub API)...[/]")
        
        skills_list = []
        takeaways_list = []
        cleaned_desc_list = []
        salary_expectations = []
        
        cache_modified = False
        
        for idx, row in track(df.iterrows(), total=len(df), description="Enhancing descriptions"):
            desc = row.get("description", "")
            desc_hash = self._get_hash(str(desc).strip())
            
            if desc_hash not in self.cache and str(desc).strip():
                # Simple rate limit mitigation
                time.sleep(0.5) # Hackclub API is usually faster and more lenient
                cache_modified = True
                
            res = self.improve_description(desc)
            
            skills_list.append(json.dumps(res.get("skills", [])))
            takeaways_list.append(json.dumps(res.get("key_takeaways", [])))
            cleaned_desc_list.append(res.get("cleaned_description", desc))
            salary_expectations.append(res.get("salary_expectation", "Not specified"))
            
            # Periodically save cache to prevent total loss on crash
            if idx > 0 and idx % 20 == 0 and cache_modified:
                self._save_cache()
                cache_modified = False
            
        if cache_modified:
            self._save_cache()
            
        df["skills"] = skills_list
        df["key_takeaways"] = takeaways_list
        df["description"] = cleaned_desc_list
        df["salary_expectation"] = salary_expectations
        
        return df

