"""
rat.cli — Command-line interface with rich terminal formatting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


def cmd_index(directories: Optional[List[str]] = None) -> None:
    """Index files from directories."""
    from rat.config import config
    from rat.crawler.db import Database
    from rat.crawler.indexer import Indexer
    target_dirs = directories if directories else config.indexed_directories
    console.print(Panel.fit(f"[bold cyan]🐀 'rat' File Indexer[/bold cyan]\nQuét các thư mục: {', '.join(target_dirs)}", border_style="cyan"))

    indexer = Indexer()
    files = indexer.discover_files(target_dirs)
    total = len(files)

    if total == 0:
        console.print("[yellow]Không tìm thấy tệp nào phù hợp để lập chỉ mục.[/yellow]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Đang lập chỉ mục {total} tệp...", total=total)

        def on_progress(done: int, tot: int, filename: str) -> None:
            progress.update(task, completed=done, description=f"Quét: [green]{filename[:25]}[/green]")

        indexed, _ = indexer.run_full_index(directories=target_dirs, progress_callback=on_progress)

    db = Database(config.db_path)
    stats = db.get_stats()
    size_mb = stats["total_size_bytes"] / (1024 * 1024)
    console.print(f"[bold green]✓ Hoàn tất![/bold green] Đã cập nhật {indexed}/{total} tệp. Tổng kho lưu trữ: {stats['total_files']} tệp (~{size_mb:.1f} MB).")


def cmd_search(
    query: str,
    limit: int = 10,
    open_first: bool = False,
    reveal_first: bool = False,
    show_trace: bool = False
) -> None:
    """Search files using natural language query with optional FR-CoT reasoning trace."""
    from rat.engine.hybrid_search import SearchEngine
    engine = SearchEngine()
    response = engine.search(query, limit=limit)

    results = response["results"]
    parsed = response["parsed_context"]
    latency = response["latency_ms"]
    sparse_count = response.get("sparse_count", 0)
    dense_count = response.get("dense_count", 0)
    hypo_text = response.get("hypo_text")

    # Filter description banner
    filter_tags = []
    if parsed.get("file_type_desc"):
        filter_tags.append(f"[blue]📁 {parsed['file_type_desc']}[/blue]")
    if parsed.get("time_desc"):
        filter_tags.append(f"[magenta]📅 {parsed['time_desc']}[/magenta]")
    if parsed.get("keywords"):
        filter_tags.append(f"[yellow]🔑 {', '.join(parsed['keywords'])}[/yellow]")

    filter_tags.append(f"[cyan]⚡ FTS5: {sparse_count} | Vectors: {dense_count}[/cyan]")

    header = f"🔍 Truy vấn: [bold white]\"{query}\"[/bold white]"
    if filter_tags:
        header += "  |  " + "  ".join(filter_tags)
    header += f"  (Tìm thấy {len(results)} tệp trong {latency}ms)"

    if hypo_text:
        header += f"\n\n[dim italic]🧠 HyDE Context:[/dim italic] [dim]\"{hypo_text[:160]}...\"[/dim]"

    console.print(Panel(header, title="🐀 True Hybrid Search (RRF + HyDE)", border_style="blue"))

    if not results:
        console.print("[yellow]Không tìm thấy tệp nào khớp với mô tả của bạn. Hãy thử quét lại (`rat index`) hoặc mô tả khác.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("#", style="dim", width=3)
    table.add_column("Tên tệp", style="bold white", width=26)
    table.add_column("Loại", style="cyan", width=6)
    table.add_column("Đã sửa", style="magenta", width=14)
    table.add_column("Lý do khớp (Context Reasoning)", style="green", width=40)
    table.add_column("Độ khớp", style="yellow", justify="right", width=9)

    for idx, item in enumerate(results, 1):
        table.add_row(
            str(idx),
            item.file_name,
            item.file_ext.upper(),
            item.modified_formatted,
            item.explanation,
            f"{int(item.score)}%"
        )

    console.print(table)

    trace = response.get("reasoning_trace")
    if trace and any(arg in sys.argv for arg in ["--trace", "-t", "--cot"]):
        console.print(Panel(trace.render_markdown(), title="🧠 FR-CoT Multi-Step Reasoning Trace", border_style="cyan"))

    if open_first and results:
        first = results[0]
        console.print(f"[bold green]⚡ Đang mở tệp:[/bold green] {first.file_path}")
        if sys.platform == "darwin":
            subprocess.run(["open", first.file_path], check=False)
        else:
            subprocess.run(["xdg-open", first.file_path], check=False)
    elif reveal_first and results:
        first = results[0]
        console.print(f"[bold green]📁 Đang mở trong Finder:[/bold green] {first.file_path}")
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", first.file_path], check=False)
        else:
            subprocess.run(["xdg-open", os.path.dirname(first.file_path)], check=False)


def cmd_ask(file_query: str, question: str) -> None:
    """Find file and ask the local AI/SLM to answer questions about its content."""
    from rat.crawler.extractors import extract_document_content
    from rat.engine.hybrid_search import SearchEngine
    from rat.engine.qa_engine import qa_engine

    engine = SearchEngine()
    response = engine.search(file_query, limit=1)
    results = response["results"]

    if not results:
        console.print(f"[yellow]Không tìm thấy file nào khớp với '{file_query}'.[/yellow]")
        return

    top_file = results[0]
    console.print(Panel.fit(
        f"📄 [bold white]{top_file.file_name}[/bold white]\n"
        f"[dim]{top_file.file_path}[/dim]\n"
        f"❓ Câu hỏi: [bold yellow]{question}[/bold yellow]",
        title="🧠 'rat' In-Situ Document Assistant",
        border_style="blue"
    ))

    with console.status("[bold green]Đang phân tích tài liệu và suy luận câu trả lời..."):
        content = extract_document_content(top_file.file_path)
        qa_result = qa_engine.answer_question(content, question, file_name=top_file.file_name)

    answer_text = qa_result["answer"]
    engine_badge = qa_result["engine"]
    console.print(Panel(
        f"{answer_text}\n\n[dim]⚡ Bộ máy xử lý: {engine_badge}[/dim]",
        title="💡 Kết quả Hỏi - Đáp Tài liệu",
        border_style="green"
    ))


def cmd_ask_file(file_path, model_path, *, db_path=None, questions=None,
                 max_context_tokens=4096) -> int:
    """One explicit indexed file, native offline inference, reusable chat session."""
    import threading
    from uuid import uuid4
    from rat.config import config
    from rat.crawler.db import Database
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.engine.selected_document_qa import answer_selected_document
    from rat.timetable.compositor import TimetableCompositor

    database = None
    current_path = Path(file_path).expanduser()

    def validate_path(path):
        if not path.is_absolute() or not path.is_file():
            raise ValueError('Cần đường dẫn tuyệt đối tới tệp đang tồn tại.')
        if not database.get_document_by_path(str(path)):
            raise ValueError('Tệp chưa có trong chỉ mục RAT; hãy lập chỉ mục thư mục đã chọn trước.')

    try:
        database = Database(db_path or config.db_path, read_only=True)
        validate_path(current_path)
        with AssistantRuntime(db=database, compositor=TimetableCompositor([]),
                document_model_path=model_path,
                document_max_context_tokens=max_context_tokens) as runtime:
            with console.status('Đang nạp model local…'):
                load_s = runtime.document_model_client.load()
            console.print(f'Model đã sẵn sàng ({load_s:.2f}s).', markup=False)

            def ask(question):
                cancelled = threading.Event()
                execution_id = 'document-cli-' + uuid4().hex
                try:
                    response = answer_selected_document(runtime, question, str(current_path),
                        should_cancel=cancelled.is_set, execution_id=execution_id)
                except KeyboardInterrupt:
                    cancelled.set()
                    runtime.cancel_execution(execution_id)
                    console.print('Đã dừng câu hỏi. Có thể hỏi tiếp.', markup=False)
                    return False
                if response.error:
                    console.print(f'Chưa trả lời được: {response.error}', markup=False)
                    return False
                console.print(response.answer, markup=False)
                for source in response.sources:
                    if source.get('path') == str(current_path) and source.get('read'):
                        scope = f"{source.get('read_chars')}/{source.get('total_chars')} ký tự"
                        suffix = ' · chỉ là trích đoạn' if source.get('truncated') else ''
                        console.print(f'Nguồn: {current_path} · {scope}{suffix}', markup=False)
                return True

            if questions:
                success = True
                for question in questions:
                    success = ask(question) and success
                return 0 if success else 1

            console.print('Hỏi về tệp đã chọn. :file /đường/dẫn đổi tệp; :unload giải phóng model; :quit thoát.',
                          markup=False)
            while True:
                try:
                    question = console.input('Bạn> ').strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if question == ':quit':
                    break
                if question == ':unload':
                    runtime.document_model_client.unload()
                    console.print('Đã giải phóng model và cache; câu hỏi tiếp theo sẽ nạp lại.', markup=False)
                elif question.startswith(':file '):
                    candidate = Path(question[6:].strip()).expanduser()
                    try:
                        validate_path(candidate)
                    except ValueError as error:
                        console.print(str(error), markup=False)
                    else:
                        current_path = candidate
                        console.print(f'Đã chọn: {current_path}', markup=False)
                elif question:
                    ask(question)
            return 0
    except KeyboardInterrupt:
        console.print('Đã dừng và đóng session.', markup=False)
        return 130
    except Exception as error:
        console.print(f'Không thể chạy session local: {error}', markup=False)
        return 1
    finally:
        if database is not None:
            connection = getattr(database._local, 'conn', None)
            if connection is not None:
                connection.close()
                database._local.conn = None


def cmd_dedup() -> None:
    """Find duplicate files and semantic document version trees."""
    from rat.crawler.dedup import dedup_engine
    from rat.engine.reranker import format_file_size, format_relative_time
    console.print(Panel.fit("[bold cyan]🌳 Smart Deduplication & Version Tree Analyzer[/bold cyan]", border_style="cyan"))

    with console.status("[bold green]Đang phân tích cấu trúc trùng lặp và các phiên bản sửa đổi..."):
        exact_dups = dedup_engine.find_exact_duplicates()
        version_trees = dedup_engine.find_version_trees(min_versions=2)

    # 1. Exact Duplicates
    if exact_dups:
        total_wasted = sum(g["wasted_space_bytes"] for g in exact_dups)
        console.print(f"\n[bold red]⚠️ Phát hiện {len(exact_dups)} nhóm tệp trùng lặp 100% (Lãng phí: ~{format_file_size(total_wasted)}):[/bold red]")
        for idx, g in enumerate(exact_dups[:10], 1):
            console.print(f"\n  [bold yellow]Nhóm {idx}:[/bold yellow] {g['copy_count']} bản sao • Kích thước: {format_file_size(g['file_size'])}")
            for f in g["files"]:
                console.print(f"    • [white]{f['file_name']}[/white]  [dim]({f['modified_formatted']})[/dim]\n      [blue]{f['file_path']}[/blue]")
    else:
        console.print("\n[bold green]✓ Không có tệp nào bị nhân bản 100% (MD5).[/bold green]")

    # 2. Semantic Version Trees
    if version_trees:
        console.print(f"\n[bold green]📁 Phát hiện {len(version_trees)} cây phiên bản tài liệu (Document Revision Trees):[/bold green]")
        for idx, vt in enumerate(version_trees[:10], 1):
            latest = vt.latest_doc
            console.print(f"\n  [bold cyan]Cây {idx}:[/bold cyan] [bold white]{vt.canonical_name.upper()}[/bold white] ({vt.file_ext}) — {vt.count} phiên bản")
            for doc in vt.documents:
                is_latest = (doc["file_path"] == latest["file_path"]) if latest else False
                badge = "[bold green]🎯 BẢN MỚI NHẤT[/bold green]" if is_latest else "[dim]Bản cũ[/dim]"
                console.print(f"    • {badge} [white]{doc['file_name']}[/white]  [dim]({format_relative_time(doc['modified_at'])})[/dim]")
                console.print(f"      [blue]{doc['file_path']}[/blue]")
    else:
        console.print("\n[dim]Không phát hiện cây phiên bản nào.[/dim]")


def cmd_stats() -> None:
    """Print indexing statistics."""
    from rat.config import config
    from rat.crawler.db import Database
    from rat.engine.slm import slm_engine
    db = Database(config.db_path)
    stats = db.get_stats()
    size_mb = stats["total_size_bytes"] / (1024 * 1024)
    slm_status = "🟢 Hoạt động (qwen2.5:1.5b)" if slm_engine.is_model_installed() else "🟡 Chưa sẵn sàng"

    console.print(Panel.fit(
        f"[bold cyan]🐀 'rat' Search Engine Status[/bold cyan]\n\n"
        f"• Tổng số tệp trong chỉ mục: [bold white]{stats['total_files']}[/bold white]\n"
        f"• Dung lượng nội dung: [bold white]{size_mb:.2f} MB[/bold white]\n"
        f"• Bộ não SLM cục bộ: [bold green]{slm_status}[/bold green]\n"
        f"• Vị trí Database: [dim]{config.db_path}[/dim]\n"
        f"• Các thư mục theo dõi: [green]{', '.join(config.indexed_directories)}[/green]",
        border_style="cyan"
    ))


def cmd_review(
    target: Optional[str] = None,
    staged: bool = False,
    repo: Optional[str] = None,
    submit: bool = False,
    repo_path: Optional[str] = None,
) -> None:
    """Run automated multi-lens code review on local diff or GitHub Pull Request."""
    from rat.kernel.capabilities.code_review import create_code_review_capability
    cap = create_code_review_capability()

    if target:
        console.print(Panel.fit(f"[bold cyan]🐀 RAT Code Review — GitHub PR {target}[/bold cyan]", border_style="cyan"))
        try:
            res = cap.operations["review_github_pr"].handler({
                "pr_target": target,
                "repo": repo,
                "submit": submit,
            })
        except Exception as e:
            console.print(f"[bold red]Lỗi khi đánh giá PR:[/bold red] {e}")
            return
    else:
        scope = "staged (--cached)" if staged else "working tree (unstaged)"
        console.print(Panel.fit(f"[bold cyan]🐀 RAT Code Review — Local Diff ({scope})[/bold cyan]", border_style="cyan"))
        try:
            res = cap.operations["review_local_diff"].handler({
                "staged": staged,
                "repo_path": repo_path,
            })
        except Exception as e:
            console.print(f"[bold red]Lỗi khi đọc diff local:[/bold red] {e}")
            return

    verdict = res.get("verdict", "UNKNOWN")
    verdict_badge = {
        "APPROVED": "[bold green]✅ APPROVED[/bold green]",
        "COMMENT_WITH_SUGGESTIONS": "[bold yellow]💬 COMMENT WITH SUGGESTIONS[/bold yellow]",
        "CHANGES_REQUESTED": "[bold red]🚨 CHANGES REQUESTED[/bold red]",
    }.get(verdict, f"[bold white]{verdict}[/bold white]")

    console.print(f"\n[bold]Kết quả:[/bold] {verdict_badge}")
    console.print(f"[dim]{res.get('summary', '')}[/dim]\n")

    findings = res.get("findings", [])
    if not findings:
        console.print("[green]🎉 Không phát hiện lỗi cú pháp, thiếu import, hay vi phạm bất biến nào.[/green]")
    else:
        table = Table(title=f"Danh sách phát hiện ({len(findings)})", border_style="dim")
        table.add_column("Mức độ", style="bold", width=12)
        table.add_column("Ống kính", width=14)
        table.add_column("Vị trí", style="cyan", width=25)
        table.add_column("Mô tả / Đề xuất sửa", style="white")

        for f in findings:
            sev = f.get("severity", "")
            sev_fmt = (
                "[red]CRITICAL[/red]" if sev == "CRITICAL"
                else "[yellow]WARNING[/yellow]" if sev == "WARNING"
                else "[blue]SUGGEST[/blue]"
            )
            loc = f"{f.get('file_path')}:{f.get('line_number') or '?'}"
            desc = f"[bold]{f.get('title')}[/bold]\n{f.get('description')}"
            if f.get("suggested_fix"):
                desc += f"\n[green]Gợi ý:[/green] [dim]{f.get('suggested_fix')}[/dim]"
            table.add_row(sev_fmt, f.get("lens", ""), loc, desc)

        console.print(table)

    if res.get("submitted"):
        console.print(f"\n[bold green]✓ Đã gửi nhận xét lên GitHub PR thành công![/bold green]")


def cmd_doctor(as_json: bool = False) -> int:
    """Run system diagnostics and verify environment, storage, models, and permissions."""
    import json
    from rat.os.diagnostics import collect_system_diagnostics
    report = collect_system_diagnostics()

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return report["exit_code"]

    status = report["overall_status"]
    status_fmt = (
        "[bold green]✓ PASS (All Systems Healthy)[/bold green]"
        if status == "PASS"
        else "[bold yellow]⚠ WARN (Minor Configuration or Permission Notices)[/bold yellow]"
        if status == "WARN"
        else "[bold red]✗ FAIL (Critical Issues Detected)[/bold red]"
    )

    console.print(Panel.fit(
        f"[bold cyan]🩺 RAT System Doctor & Diagnostics[/bold cyan]\n"
        f"Overall Health: {status_fmt}",
        border_style="cyan"
    ))

    table = Table(title="Diagnostic Checks", border_style="dim")
    table.add_column("Component", style="bold", width=16)
    table.add_column("Status", width=10)
    table.add_column("Details & Recommendations", style="white")

    for comp_name, comp_data in report["checks"].items():
        st = comp_data.get("status", "UNKNOWN")
        st_badge = (
            "[green]PASS[/green]" if st == "PASS"
            else "[yellow]WARN[/yellow]" if st == "WARN"
            else "[red]FAIL[/red]"
        )
        details = comp_data.get("details", {})
        info_lines = []
        if comp_name == "environment":
            info_lines.append(f"Python {details.get('python_version')} on {details.get('platform')}")
            if details.get("is_apple_silicon"):
                info_lines.append("[cyan]Apple Silicon (arm64)[/cyan]")
        elif comp_name == "database":
            if details.get("exists"):
                size_mb = details.get("size_bytes", 0) / (1024 * 1024)
                info_lines.append(f"Integrity: {details.get('integrity')}, {details.get('total_documents')} documents (~{size_mb:.1f} MB)")
            else:
                info_lines.append("[yellow]No database file created yet[/yellow]")
        elif comp_name == "configuration":
            info_lines.append(f"Profile: [bold]{details.get('default_profile')}[/bold], Active folders: {details.get('active_directories_found')}")
        elif comp_name == "models":
            info_lines.append(f"Provider: {details.get('provider')}, SLM installed: {'Yes' if details.get('slm_model_installed') else 'No'}")
        elif comp_name == "permissions":
            info_lines.append(f"Accessibility: {'Granted' if details.get('trusted') else 'Not Granted'}")

        if comp_data.get("message"):
            info_lines.append(f"[yellow]{comp_data['message']}[/yellow]")
        if comp_data.get("error"):
            info_lines.append(f"[bold red]Error: {comp_data['error']}[/bold red]")

        table.add_row(comp_name.capitalize(), st_badge, "\n".join(info_lines))

    console.print(table)
    return report["exit_code"]


def main() -> None:
    parser = argparse.ArgumentParser(description="rat — Smart Local File Finder with Context Engineering & SLM")
    subparsers = parser.add_subparsers(dest="command")

    # Index command
    index_parser = subparsers.add_parser("index", help="Scan and index folders")
    index_parser.add_argument("dirs", nargs="*", help="Optional directories to index")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search files with natural language")
    search_parser.add_argument("query", help="Natural language query description")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="Max results")
    search_parser.add_argument("-o", "--open", action="store_true", help="Open best matching file")
    search_parser.add_argument("-f", "--finder", action="store_true", help="Reveal best match in Finder")
    search_parser.add_argument("-t", "--trace", "--cot", dest="trace", action="store_true", help="Display FR-CoT Multi-Step Reasoning Trace")

    # Ask SLM command
    ask_parser = subparsers.add_parser("ask", help="Ask local SLM a question about a file")
    ask_parser.add_argument("file_query", help="Query to identify the file")
    ask_parser.add_argument("question", help="Question to ask about the file")

    file_parser = subparsers.add_parser("ask-file", help="Chat offline about one exact indexed file using native MLX")
    file_parser.add_argument("file_path", help="Absolute path of an already indexed file")
    file_parser.add_argument("--model-path", required=True, help="Complete local MLX model directory; no downloads")
    file_parser.add_argument("--db", help="Existing RAT index database")
    file_parser.add_argument("-q", "--question", action="append", help="Repeat for batch questions; omit for interactive chat")
    file_parser.add_argument("--max-context-tokens", type=int, default=4096)

    # Dedup & Version Tree command
    subparsers.add_parser("dedup", help="Find duplicate files and document revision trees")

    # Status command
    subparsers.add_parser("status", help="Show index statistics")

    # Review command
    review_parser = subparsers.add_parser("review", help="Automated multi-lens code review on local diff or GitHub PR")
    review_parser.add_argument("target", nargs="?", default=None, help="Optional GitHub PR number, URL, or owner/repo#pr")
    review_parser.add_argument("--staged", action="store_true", help="Review staged changes instead of unstaged diff")
    review_parser.add_argument("--repo", default=None, help="GitHub repo (e.g. owner/repo) if reviewing remote PR")
    review_parser.add_argument("--submit", action="store_true", help="Submit review comment to GitHub PR via gh CLI")

    # Doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run comprehensive diagnostic health checks")
    doctor_parser.add_argument("--json", action="store_true", help="Output raw JSON schema")

    args = parser.parse_args()

    if args.command == "index":
        cmd_index(args.dirs if args.dirs else None)
    elif args.command == "search":
        cmd_search(args.query, limit=args.limit, open_first=args.open, reveal_first=args.finder, show_trace=getattr(args, "trace", False))
    elif args.command == "ask":
        cmd_ask(args.file_query, args.question)
    elif args.command == "ask-file":
        raise SystemExit(cmd_ask_file(args.file_path, args.model_path, db_path=args.db,
            questions=args.question, max_context_tokens=args.max_context_tokens))
    elif args.command == "dedup":
        cmd_dedup()
    elif args.command == "status":
        cmd_stats()
    elif args.command == "review":
        cmd_review(args.target, staged=args.staged, repo=args.repo, submit=args.submit)
    elif args.command == "doctor":
        raise SystemExit(cmd_doctor(as_json=args.json))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
