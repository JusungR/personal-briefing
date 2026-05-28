/**
 * Daily Briefing 자동 발송 스크립트
 *
 * 동작 방식:
 *   Claude Code가 생성한 "[Daily Briefing]" 제목의 Gmail 초안을 찾아
 *   자동으로 발송합니다.
 *
 * 최초 설정 순서:
 *   1. script.google.com → 새 프로젝트 생성
 *   2. 프로젝트 설정(⚙️) → 시간대를 "Asia/Seoul"로 변경 후 저장
 *   3. 이 파일 내용을 편집기에 붙여넣기
 *   4. 함수 선택 드롭다운에서 "setupTrigger" 선택 후 실행 (최초 1회만)
 *      → Gmail 권한 승인 팝업이 뜨면 허용
 *   5. 이후 매일 오전 8시에 자동 실행됩니다.
 */

var SUBJECT_PREFIX = '[Daily Briefing]';

// ─────────────────────────────────────────
// 메인: 초안 검색 → 발송
// ─────────────────────────────────────────
function sendDailyBriefingDraft() {
  var drafts = GmailApp.getDrafts();
  var sent = 0;

  for (var i = 0; i < drafts.length; i++) {
    var draft = drafts[i];
    var subject = draft.getMessage().getSubject();

    if (subject.indexOf(SUBJECT_PREFIX) === 0) {
      draft.send();
      Logger.log('발송 완료: ' + subject);
      sent++;
    }
  }

  if (sent === 0) {
    Logger.log('발송할 Daily Briefing 초안 없음 (' + new Date() + ')');
  }
}

// ─────────────────────────────────────────
// 초기 설정: 트리거 등록 (최초 1회 실행)
// ─────────────────────────────────────────
function setupTrigger() {
  // 기존 등록된 트리거 전체 삭제
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }

  // 매일 오전 8:00~9:00 (Asia/Seoul) 실행
  ScriptApp.newTrigger('sendDailyBriefingDraft')
    .timeBased()
    .everyDays(1)
    .atHour(8)
    .create();

  Logger.log('트리거 등록 완료: 매일 오전 8~9시 (Asia/Seoul) 자동 실행');
}

// ─────────────────────────────────────────
// 트리거 삭제 (비활성화할 때 사용)
// ─────────────────────────────────────────
function removeTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  Logger.log('모든 트리거 삭제 완료');
}
