"""
TV 동기화 — GET /api/v1/sync/scores?cursor=  (devlog 054 §4, 060)

응답:
  scores   커서 뒤로 바뀌었거나 새로 보이게 된 악보 (기준 시각 순, 한 번에 SYNC_PAGE_SIZE 개)
  ids      지금 이 사람이 볼 수 있는 악보 id **전부** — TV 는 여기 없는 악보를 지운다
  cursor   다음에 보낼 값 (불투명)
  has_more 남은 변경이 있다 → 곧바로 cursor 로 다시

지운 악보를 목록(deleted)으로 주지 않고 ids 로 푸는 이유: TV 가 악보를 잃는 길은 삭제 말고도
앙상블 나가기 · 내보내기 · 앙상블 삭제 · 개인 악보로 옮기기가 있다. 길마다 삭제 기록을 남기면 하나를 빠뜨리기 쉽다.
"지금 볼 수 있는 것 전부"는 어떤 길로 잃든 맞다. id 몇백 개는 가볍다.

기준 시각(effective) = max(악보 updated_at, 내가 그 앙상블에 들어온 시각)
  — 앙상블에 새로 들어가면 그 앙상블의 옛 악보가 "새로 보이게 된 것"으로 잡힌다.
  새 판 · 메타데이터 수정 · 쪽수/해시 채움 · 앙상블 옮기기는 모두 updated_at 을 바꾼다.

늦은 커밋: 커서를 넘긴 뒤 그보다 이른 시각으로 커밋되는 변경을 놓치지 않게, 최근 SYNC_LAG_SECONDS 안의 변경은 다음 번으로 미룬다.
"""
import base64
import binascii
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import DateTimeField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from ensembles.models import Membership
from .models import Score


class BadCursor(ValueError):
    pass


def encode_cursor(moment, score_id):
    raw = json.dumps({'t': moment.isoformat(), 'i': score_id}, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def decode_cursor(cursor):
    """(시각, id) 또는 None(처음). 깨진 값은 BadCursor"""
    if not cursor:
        return None
    try:
        padded = cursor + '=' * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        moment = datetime.fromisoformat(data['t'])
        if timezone.is_naive(moment):
            raise ValueError('naive')
        return moment, int(data['i'])
    except (binascii.Error, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BadCursor('Invalid cursor') from exc


def readable_with_effective_time(user):
    my_join = Membership.objects.filter(ensemble=OuterRef('ensemble'), user=user).values('joined_at')[:1]
    return (Score.objects.readable_by(user)
            .annotate(effective=Greatest('updated_at', Coalesce(Subquery(my_join, output_field=DateTimeField()),
                                                                'updated_at')))
            .select_related('ensemble', 'current_version'))


def changes(user, cursor=None, limit=None):
    """→ dict(scores=[Score…], ids=[…], cursor=str|None, has_more=bool)"""
    limit = limit or settings.SYNC_PAGE_SIZE
    position = decode_cursor(cursor)
    horizon = timezone.now() - timedelta(seconds=settings.SYNC_LAG_SECONDS)

    queryset = readable_with_effective_time(user).filter(effective__lte=horizon)
    if position is not None:
        moment, last_id = position
        queryset = queryset.filter(Q(effective__gt=moment) | Q(effective=moment, id__gt=last_id))
    rows = list(queryset.order_by('effective', 'id')[:limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]

    if rows:
        next_cursor = encode_cursor(rows[-1].effective, rows[-1].id)
    else:
        next_cursor = cursor or None   # 바뀐 것이 없으면 그대로 (처음이면 아직 없음)

    ids = sorted(Score.objects.readable_by(user).values_list('id', flat=True))
    return {'scores': rows, 'ids': ids, 'cursor': next_cursor, 'has_more': has_more}
