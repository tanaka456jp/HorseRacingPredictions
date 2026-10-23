"""Point-in-time, strictly odds-free JRA Friday top-three article renderer.

Consumes *already licensed, verified, curated* race/horse inputs. Does not
obtain entries, fit a model, query odds, post to note, or authorize publication.
Real article output must still pass independent source, completeness, and
note-magazine publication gates. No fabricated runners or model estimates.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from urllib.parse import urlparse, unquote
from typing import Any, Mapping
from unicodedata import normalize
import re

_DISALLOWED = re.compile(
    r"odds|popularity|market_rank|market_share|betting|payout|dividend"
    r"|オッズ|人気|投票|払戻|配当", re.IGNORECASE
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
# Existing field-key rejection is insufficient: market data could be hidden
# inside a permitted factor's human-language finding or source URL.
_MARKET_NARRATIVE = re.compile(
    r"odds|popular(?:ity)?|market[_ -]?(?:rank|share|odds)|"
    r"betting|payout|dividend|"
    r"オッズ|人気(?:順|順位|馬)?|単勝|複勝|払戻|配当|馬券|投票数|支持率",
    re.IGNORECASE,
)


def _reject_market_narrative(value: str, label: str) -> None:
    canonical = normalize("NFKC", value)
    # Ignore separating spaces and zero-width characters.
    searchable = re.sub(r"[\s\u200b-\u200d\u2060\ufeff]+", "", canonical)
    if _MARKET_NARRATIVE.search(searchable):
        _fail(f"{label}: market/odds/popularity evidence is forbidden")


_ALLOWED_FACTORS = frozenset({
    "近走内容", "距離適性", "コース適性", "血統", "調教",
    "騎手", "枠順", "脚質・展開", "馬場・天候", "休養・ローテ",
})
_ID = re.compile(r"JRA-[0-9]{8}-[0-9A-Za-z-]{1,24}\Z")
_HORSE = frozenset({"name", "number", "strength", "upside_score", "upside_signals", "factors"})
_FACTOR = frozenset({"category", "finding", "source_url", "observed_at"})
_RACE = frozenset({
    "race_id", "title", "course", "post_at", "status", "horses",
})
_DOC = frozenset({
    "issue_date", "generated_at", "model_id", "model_frozen_at",
    "input_approved_for_research", "complete_race_manifest",
    "expected_race_ids", "races",
})


class ForecastInputError(ValueError):
    """Insufficient or post-decision / market-contaminated evidence."""


def _fail(message: str) -> None:
    raise ForecastInputError(message)


def _clock(text: Any, label: str) -> datetime:
    if type(text) is not str:
        _fail(f"{label}: timezone-aware time is required")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", text):
        _fail(f"{label}: canonical ISO time with offset is required")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{label}: invalid timestamp")
    if value.utcoffset() is None:
        _fail(f"{label}: timezone is missing")
    return value.astimezone(timezone.utc)


def _no_market_data(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _DISALLOWED.search(str(key)):
                _fail("odds/popularity/payout fields are forbidden")
            _no_market_data(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _no_market_data(item)


def _limit_text(text: Any, label: str, maximum: int = 180) -> str:
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= maximum:
        _fail(f"{label}: valid nonempty short text required")
    return text.strip().replace("\n", " ")


def _source_url(value: Any) -> str:
    if type(value) is not str:
        _fail("factor evidence URL is missing")
    parsed = urlparse(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment):
        _fail("factor evidence requires an HTTPS URL without embedded credentials")
    _reject_market_narrative(unquote(value), "factor evidence URL")
    return value


def render_friday_jra_article(doc: Mapping[str, Any]) -> str:
    """Generate reviewable Markdown with 3 distinct picks and 1 non-market outsider.

    The outsider is *not* an inferred low-popularity runner: it is the
    highest independently frozen condition-upside signal among horses
    outside the top-three strength picks. All evidence must predate issue.
    """
    if not isinstance(doc, Mapping) or set(doc) != _DOC:
        _fail("article envelope mismatch")
    _no_market_data(doc)
    if doc["input_approved_for_research"] is not True:
        _fail("independently approved research source is required")
    if doc["complete_race_manifest"] is not True:
        _fail("complete JRA race manifest evidence is required")
    issue = doc["issue_date"]
    if type(issue) is not str or not _DATE.fullmatch(issue):
        _fail("issue_date must be YYYY-MM-DD")
    try:
        issue_day = datetime.strptime(issue, "%Y-%m-%d").date()
    except ValueError:
        _fail("issue_date is invalid")
    if issue_day.weekday() != 4:
        _fail("article must be a Friday issue")
    issued = _clock(doc["generated_at"], "generated_at")
    frozen = _clock(doc["model_frozen_at"], "model_frozen_at")
    jst = timezone(timedelta(hours=9))
    if issued.astimezone(jst).date() != issue_day:
        _fail("generation must be on issue Friday in JST")
    if issued.astimezone(jst).hour < 12 or issued.astimezone(jst).hour > 23:
        _fail("Friday publication requires a post-noon source inspection")
    if frozen >= issued:
        _fail("model must be frozen before article generation")
    model = _limit_text(doc["model_id"], "model_id", 80)
    _reject_market_narrative(model, "model_id")
    expected = doc["expected_race_ids"]
    races = doc["races"]
    if not isinstance(expected, list) or not expected or len(expected) > 72:
        _fail("nonempty bounded expected race manifest required")
    if (not all(type(x) is str and _ID.fullmatch(x) for x in expected)
            or len(set(expected)) != len(expected)):
        _fail("duplicate/invalid expected race IDs")
    if not isinstance(races, list) or len(races) != len(expected):
        _fail("missing races relative to fixed schedule manifest")
    if {r.get("race_id") for r in races if isinstance(r, Mapping)} != set(expected):
        _fail("observed races do not exactly match frozen manifest")

    header = [
        f"# {issue}発行｜JRA週末レース・オッズ非依存の上位3着予想＋穴馬1頭",
        "",
        f"予想基準日：{issue}（金曜日）　モデル識別子：{model}",
        "",
        "本予想は人気順位・投票数・オッズ・払戻額を予測因子に使用していません。"
        "すべての順位はレース前の非市場データから計算したモデル内の相対強度に基づく推定であり、"
        "的中や利益を保証しません。予測精度や収益性の独立した確認が済んでいない場合、確率の校正済み主張は行いません。",
        "",
        "日曜日の枠順が金曜時点で未確定の場合は**暫定予想**です。"
        "枠順の確定を装った表示は行いません。",
        "",
        "穴馬は市場人気の低さを示す意味ではなく、上位3着候補の外から、"
        "条件がかみ合う場合の上振れ余地を別軸で評価した**伏兵候補**です。"
        "人気・オッズの低さを確認した馬ではありません。",
        "",
    ]
    for race in sorted(races, key=lambda r: (r["post_at"], r["race_id"])):
        if not isinstance(race, Mapping) or set(race) != _RACE:
            _fail("invalid race fields")
        rid = race["race_id"]
        title = _limit_text(race["title"], "race title")
        course = _limit_text(race["course"], "race course")
        post = _clock(race["post_at"], "post_at")
        if post <= issued:
            _fail("race must not have started when article is generated")
        race_day = post.astimezone(jst).date()
        if race_day not in (issue_day + timedelta(days=1),
                            issue_day + timedelta(days=2)):
            _fail("only immediate Saturday/Sunday JRA races allowed")
        status = race["status"]
        if status not in ("confirmed", "provisional"):
            _fail("race status must be confirmed or provisional")
        if race_day == issue_day + timedelta(days=2) and status != "provisional":
            _fail("Friday's Sunday card must be labeled provisional")
        if race_day == issue_day + timedelta(days=1) and status != "confirmed":
            _fail("Saturday must have confirmed numbered entries")
        horses = race["horses"]
        if not isinstance(horses, list) or not 4 <= len(horses) <= 18:
            _fail("all declared runners, 4-18, required")
        names, numbers, scored = set(), set(), []
        for h in horses:
            if not isinstance(h, Mapping) or set(h) != _HORSE:
                _fail("invalid runner fields")
            name = _limit_text(h["name"], "horse name", 60)
            if name in names:
                _fail("duplicate horse name")
            names.add(name)
            number = h["number"]
            if status == "confirmed":
                if type(number) is not int or not 1 <= number <= 18 or number in numbers:
                    _fail("confirmed card requires unique horse numbers")
                numbers.add(number)
            elif number is not None:
                _fail("provisional card must not assign unconfirmed horse numbers")
            strength = h["strength"]
            if type(strength) not in (float, int) or not isfinite(strength) or strength <= 0:
                _fail("strictly positive finite precomputed strength required")
            upside_score = h["upside_score"]
            if (type(upside_score) not in (float, int)
                    or not isfinite(upside_score) or upside_score <= 0):
                _fail("strictly positive finite frozen condition-upside score required")
            upside_signals = h["upside_signals"]
            if (not isinstance(upside_signals, list)
                    or not 2 <= len(upside_signals) <= 5
                    or any(type(tag) is not str or tag not in _ALLOWED_FACTORS
                           for tag in upside_signals)
                    or len(set(upside_signals)) != len(upside_signals)):
                _fail("two to five distinct approved upside factor categories required")
            factors = h["factors"]
            if not isinstance(factors, list) or not 3 <= len(factors) <= 10:
                _fail("each runner needs three or more independent factor categories")
            categories, evidence = set(), []
            for f in factors:
                if not isinstance(f, Mapping) or set(f) != _FACTOR:
                    _fail("invalid factor evidence fields")
                category = f["category"]
                if category not in _ALLOWED_FACTORS or category in categories:
                    _fail("factor categories must be diverse and unique")
                categories.add(category)
                observation = _clock(f["observed_at"], "factor observed_at")
                if observation > issued or observation > post:
                    _fail("post-publication/post-race evidence cannot enter forecast")
                finding = _limit_text(f["finding"], "factor finding", 220)
                _reject_market_narrative(finding, "factor finding")
                evidence.append((category, finding, _source_url(f["source_url"])))
            if not set(upside_signals).issubset(categories):
                _fail("upside signals require the same horse's verified factor evidence")
            scored.append((float(strength), name, number, evidence,
                           float(upside_score), frozenset(upside_signals)))
        scored.sort(key=lambda v: (-v[0], v[1]))
        label = "土曜・確定馬番" if status == "confirmed" else "日曜・枠番未確定の暫定予想"
        header.extend([f"## {title}（{course}／{label}）", "", f"レースID：{rid}", ""])
        for rank, (strength, name, number, factors, _upside, _signals) in enumerate(scored[:3], start=1):
            horse_label = f"{number}番 {name}" if number is not None else name
            header.extend([f"### {rank}着予想：{horse_label}", ""])
            for category, finding, url in factors:
                header.append(f"- **{category}**：{finding}（[情報源]({url})）")
            header.append("")
        # The separate pick must never overlap the three ordered predictions.
        # Every entrant has an upside assessment made without market features.
        outsider = sorted(scored[3:], key=lambda v: (-v[4], -v[0], v[1]))[0]
        _, outsider_name, outsider_number, outsider_factors, _, outsider_signals = outsider
        outsider_label = (f"{outsider_number}番 {outsider_name}"
                          if outsider_number is not None else outsider_name)
        header.extend([f"### 穴馬1頭（非市場型の伏兵候補）：{outsider_label}", ""])
        header.append("モデルの通常評価では上位3頭の外ですが、以下の条件がかみ合う際の"
                      "上振れ要因を別軸で評価しました。")
        header.append("")
        for category, finding, url in outsider_factors:
            if category in outsider_signals:
                header.append(f"- **{category}・上振れ根拠**：{finding}（[情報源]({url})）")
            else:
                header.append(f"- **{category}**：{finding}（[情報源]({url})）")
        header.append("")
        header.append(
            "※ 伏兵とは条件変化により好走し得る候補の意味です。"
            "人気薄・高配当・プラス期待値という意味ではありません。"
        )
        header.append("")
        header.append(
            "※ 相対強度は既定モデルの事前出力です。上の1～3着は強度順の仮説であり、"
            "厳密な着順別確率や3連単的中確率を表したものではありません。"
        )
        header.append("")
    header.extend([
        "## 方法と限界", "",
        "- 採点根拠：市場・人気・オッズを除いた事前に凍結済みモデルの相対強度。",
        "- 表示対象：当週開催予定として事前に確認できた全JRAレース。欠損時は本稿を公開しません。",
        "- 日曜は金曜時点の暫定順位です。出走取消・枠番確定・天候変更等で前提が変わります。",
        "- 予想の独立評価：実際のレース結果と照合し、着順一致率・上位3頭一致率に加え、"
        "別枠の穴馬候補の3着以内率も記録します。",
        "- 穴馬候補は上位3着予想と重複させず、全出走馬の非市場由来の条件上振れ評価から選びます。",
        "- 投票行動やオッズを利用した予想ではなく、購入を勧めるものでもありません。",
        "",
    ])
    return "\n".join(header)
