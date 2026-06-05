from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorReport:
    title: str
    summary: str
    code: str
    hint: str
    detail: str | None = None


def print_error_report(
    title: str,
    summary: str,
    *,
    code: str = "UNKNOWN_ERROR",
    hint: str = "表示された詳細を添えて再実行してください。",
    detail: str | None = None,
) -> None:
    print(f"❌ {title}")
    print(f"   要点: {summary}")
    print(f"   コード: {code}")
    print(f"   対処: {hint}")
    if detail:
        for line in str(detail).splitlines():
            print(f"   詳細: {line}")


def describe_exception(error: Exception) -> ErrorReport:
    detail = str(error) or None

    if isinstance(error, FileNotFoundError):
        return ErrorReport(
            title="ファイルが見つかりません",
            summary="必要なファイルまたはフォルダがありません。",
            code="FILE_NOT_FOUND",
            hint="設定ファイルと対象フォルダの配置を確認してから、もう一度実行してください。",
            detail=detail,
        )

    if isinstance(error, PermissionError):
        return ErrorReport(
            title="アクセスできません",
            summary="ファイルやフォルダを操作する権限がありません。",
            code="PERMISSION_DENIED",
            hint="開いているアプリを閉じてから再実行し、必要なら管理者権限で試してください。",
            detail=detail,
        )

    if isinstance(error, OSError):
        if getattr(error, "winerror", None) in {5, 32}:
            return ErrorReport(
                title="別のアプリが使っています",
                summary="対象ファイルまたはフォルダがロックされています。",
                code="WIN_FILE_LOCKED",
                hint="該当ファイルを開いているアプリを閉じてから、もう一度実行してください。",
                detail=detail,
            )

        return ErrorReport(
            title="OS エラーが発生しました",
            summary="ファイル操作に失敗しました。",
            code="OS_ERROR",
            hint="対象フォルダの状態を確認してから再実行してください。",
            detail=detail,
        )

    if isinstance(error, ValueError):
        return ErrorReport(
            title="設定値に問題があります",
            summary="config.json5 または入力値の内容に問題があります。",
            code="INVALID_VALUE",
            hint="設定ファイルの該当項目を見直してから再実行してください。",
            detail=detail,
        )

    return ErrorReport(
        title="処理に失敗しました",
        summary="予期しないエラーが発生しました。",
        code="UNKNOWN_ERROR",
        hint="表示された詳細を添えて再実行してください。",
        detail=detail,
    )
