"""CLI entry points for CCG Collab."""
import sys


def main():
    """Main CLI entry point with subcommand routing."""
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("ccg - Claude-Codex-Gemini Collaboration CLI")
        print("\nUsage: ccg <subcommand> [args...]")
        print("\nSubcommands:")
        print("  discuss    Discussion orchestration (ccg-discuss)")
        print("  event      Event management (ccg-event)")
        print("\nExamples:")
        print("  ccg discuss --topic 'Review PR #123'")
        print("  ccg event discussion_started claude TASK-1 'Started'")
        return 0

    subcommand = sys.argv[1]
    if subcommand == 'discuss':
        from ccg_collab.cli.discuss import main as discuss_main
        sys.argv = ['ccg-discuss'] + sys.argv[2:]
        return discuss_main()
    elif subcommand == 'event':
        from ccg_collab.cli.event import main as event_main
        sys.argv = ['ccg-event'] + sys.argv[2:]
        return event_main()
    else:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        print("Run 'ccg --help' for usage", file=sys.stderr)
        return 1
