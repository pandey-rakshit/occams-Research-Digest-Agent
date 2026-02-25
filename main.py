import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.logging_config import setup_logging


def parse_args():
    parser = argparse.ArgumentParser(description="Research Digest Agent")
    parser.add_argument("--urls", nargs="*", default=[], help="URLs to process")
    parser.add_argument(
        "--folder", type=str, default=None, help="Folder with .txt/.html files"
    )
    parser.add_argument("--output", type=str, default="output", help="Output directory")
    return parser.parse_args()


def collect_local_files(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)

    paths = []
    for ext in ["*.txt", "*.html", "*.htm"]:
        paths.extend(glob.glob(os.path.join(folder, ext)))
    return sorted(paths)


def main():
    args = parse_args()
    setup_logging()

    urls = args.urls or []
    local_paths = collect_local_files(args.folder) if args.folder else []

    if not urls and not local_paths:
        print("Error: No sources provided. Use --urls or --folder.")
        sys.exit(1)

    from src.orchestrator import ResearchDigestOrchestrator

    orchestrator = ResearchDigestOrchestrator()
    result = orchestrator.run(
        urls=urls, local_paths=local_paths, output_dir=args.output
    )

    if result["status"] == "success":
        print(f"[+] Output saved to: {args.output}/")
        print(f"    - {args.output}/digest.md")
        print(f"    - {args.output}/sources.json")
        print(f"    - logs/pipeline.log")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
