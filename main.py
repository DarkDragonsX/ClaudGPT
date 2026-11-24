"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent / "bot_modules"
MODULE_ORDER = (
    "01_configuration.py",
    "02_database.py",
    "03_runtime.py",
    "04_ai_engine.py",
    "05_tools_and_delivery.py",
    "06_chat_routes.py",
    "07_files_and_pdf.py",
    "08_subscriptions_and_commands.py",
    "09_maintenance.py",
    "10_admin.py",
    "11_project_review.py",
    "12_message_handlers.py",
    "13_server.py",
)

for module_name in MODULE_ORDER:
    module_path = MODULE_DIR / module_name
    if not module_path.is_file():
        raise RuntimeError(f"ملف أساسي مفقود من المشروع: {module_path}")
    module_source = module_path.read_text(encoding="utf-8")
    exec(compile(module_source, str(module_path), "exec"), globals(), globals())

