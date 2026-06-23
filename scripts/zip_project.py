import os
import zipfile
from pathlib import Path

def zip_project(output_filename="airbnb_analytics_platform.zip"):
    project_root = Path(__file__).resolve().parents[1]
    
    # Files and folders to exclude
    exclude_dirs = {
        ".venv", ".git", "__pycache__", ".agents", ".codegraph", ".gemini", 
        ".dagster", ".cache", "dbt_packages", "target"
    }
    exclude_files = {
        ".env", ".env.local", "secrets.toml", "airbnb_analytics.duckdb",
        "airbnb_analytics.duckdb.wal", output_filename
    }
    
    print(f"Zipping project from: {project_root}")
    print(f"Excluding directories: {exclude_dirs}")
    print(f"Excluding files: {exclude_files}\n")
    
    zip_path = project_root / output_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            # Exclude folders
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                # Exclude files
                if file in exclude_files or file.endswith(('.duckdb', '.wal', '.zip', '.joblib', '.pkl')):
                    continue
                
                # Check for hidden files in .streamlit like secrets.toml
                full_path = Path(root) / file
                rel_path = full_path.relative_to(project_root)
                
                if "secrets.toml" in str(rel_path) or ".env" in str(rel_path):
                    continue
                
                print(f"Adding: {rel_path}")
                zipf.write(full_path, rel_path)
                
    print(f"\nSuccessfully created zip file: {zip_path}")

if __name__ == "__main__":
    zip_project()
