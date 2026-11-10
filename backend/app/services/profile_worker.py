"""Bounded persistent-event consumer with cooperative application shutdown."""
import logging
from app.core.db import transaction,rows,one,run,now

def drain_once(limit=20):
    from app.api.profiles import mine,classroom
    with transaction() as db:
        candidates=rows(db,"SELECT student_id,min(created_at) AS oldest FROM profile_refresh_events WHERE status='pending' OR (status='failed' AND julianday(coalesce(processed_at,created_at))<julianday('now','-1 minute')) GROUP BY student_id ORDER BY oldest LIMIT :n",n=limit)
    handled=0
    for event in candidates:
        try:
            with transaction() as db:
                user=one(db,"SELECT * FROM users WHERE id=:u AND role='student'",u=event['student_id'])
                classes=rows(db,"SELECT c.*,u.id AS teacher_id FROM memberships m JOIN classes c ON c.id=m.class_id JOIN users u ON u.id=c.owner_id WHERE m.user_id=:u AND m.status='active'",u=event['student_id'])
            if not user: continue
            result=mine(user)
            if result['data_quality']['status']!='current': continue
            for c in classes:
                with transaction() as db: teacher=one(db,'SELECT * FROM users WHERE id=:u',u=c['teacher_id'])
                class_result=classroom(c['id'],teacher)
                if class_result['data_quality']['status']!='current': raise RuntimeError('Class profile remains stale')
            handled+=1
        except Exception:
            logging.getLogger(__name__).exception('Background profile refresh failed')
            with transaction() as db:
                run(db,"UPDATE profile_refresh_events SET status='failed',error='后台画像刷新失败，可重试',processed_at=:t WHERE student_id=:u AND source_watermark=(SELECT max(source_watermark) FROM profile_refresh_events WHERE student_id=:u)",t=now(),u=event['student_id'])
    return handled
