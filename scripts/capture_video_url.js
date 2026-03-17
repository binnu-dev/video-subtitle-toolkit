/**
 * CDP Video URL Capture Script
 * 
 * Edge 디버그 모드(--remote-debugging-port=9222)에 CDP WebSocket으로 연결하여
 * 페이지 새로고침 시 발생하는 비디오 관련 네트워크 요청 URL을 캡처합니다.
 * 
 * 사용법:
 *   node capture_video_url.js <URL_SUBSTRING> [WAIT_SECONDS]
 * 
 * 예시:
 *   node capture_video_url.js "2033023"           # X 트윗 ID로 탭 검색, 20초 대기
 *   node capture_video_url.js "x.com/user" 30     # 30초 대기
 * 
 * 전제 조건:
 *   - Edge가 --remote-debugging-port=9222 로 실행 중
 *   - npm 패키지 'ws' 설치 (npm install -g ws 또는 로컬)
 *   - 해당 URL이 이미 브라우저 탭에 열려 있어야 함
 * 
 * 출력:
 *   캡처된 비디오 URL 목록 (video.twimg.com, .mp4, .m3u8 등)
 *   마스터 m3u8 URL → ffmpeg -i "URL" -c copy output.mp4 로 다운로드 가능
 */

const WebSocket = require('ws');
const http = require('http');

const urlSubstring = process.argv[2];
const waitSeconds = parseInt(process.argv[3]) || 20;

if (!urlSubstring) {
  console.error('Usage: node capture_video_url.js <URL_SUBSTRING> [WAIT_SECONDS]');
  console.error('  URL_SUBSTRING: 브라우저 탭 URL에 포함된 문자열 (예: 트윗 ID)');
  console.error('  WAIT_SECONDS:  네트워크 캡처 대기 시간 (기본: 20초)');
  process.exit(1);
}

// 1. CDP JSON API로 해당 URL이 열린 탭 찾기
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', c => data += c);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const targetPage = pages.find(p => p.url.includes(urlSubstring));
    if (!targetPage) {
      console.error(`ERROR: No tab found matching "${urlSubstring}"`);
      console.error('Open tabs:');
      pages.filter(p => p.type === 'page').forEach(p => console.error(`  ${p.url}`));
      process.exit(1);
    }

    console.log(`Tab found: ${targetPage.url}`);
    console.log(`Connecting to: ${targetPage.webSocketDebuggerUrl}`);
    captureVideoUrls(targetPage.webSocketDebuggerUrl);
  });
}).on('error', e => {
  console.error(`Cannot connect to CDP at port 9222: ${e.message}`);
  console.error('Edge가 --remote-debugging-port=9222 모드로 실행 중인지 확인하세요.');
  process.exit(1);
});

function captureVideoUrls(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const videoUrls = [];
  let msgId = 1;

  function send(method, params = {}) {
    const id = msgId++;
    ws.send(JSON.stringify({ id, method, params }));
    return id;
  }

  // 비디오 관련 URL 패턴
  const VIDEO_PATTERNS = [
    'video.twimg.com',
    '.mp4',
    '.m3u8',
    'amplify_video',
    'ext_tw_video',
    'video.brdcdn.com',
    'video-weaver',
    'googlevideo.com',
  ];

  function isVideoUrl(url) {
    return VIDEO_PATTERNS.some(pattern => url.includes(pattern));
  }

  ws.on('open', () => {
    console.log('Connected to CDP');
    // Network 도메인 활성화
    send('Network.enable');

    // 1초 후 페이지 새로고침 → 비디오 리소스가 다시 로드됨
    setTimeout(() => {
      console.log('Reloading page...');
      send('Page.reload');
    }, 1000);

    // 지정 시간 후 결과 출력 및 종료
    setTimeout(() => {
      const unique = [...new Set(videoUrls)];

      // m3u8 마스터 플레이리스트 찾기 (variant_version 포함 = 마스터)
      const masterM3u8 = unique.filter(u => u.includes('.m3u8') && u.includes('variant_version'));
      const allM3u8 = unique.filter(u => u.includes('.m3u8'));
      const mp4Direct = unique.filter(u => u.match(/\.mp4($|\?)/));

      console.log('\n========================================');
      console.log('=== CAPTURED VIDEO URLs ===');
      console.log('========================================');

      if (masterM3u8.length > 0) {
        console.log('\n🎯 MASTER M3U8 (use this with ffmpeg):');
        masterM3u8.forEach(u => console.log(`  ${u}`));
        console.log('\n📋 Download command:');
        console.log(`  ffmpeg -y -i "${masterM3u8[0]}" -c copy output.mp4`);
      } else if (allM3u8.length > 0) {
        console.log('\n📺 M3U8 streams:');
        allM3u8.forEach(u => console.log(`  ${u}`));
      }

      if (mp4Direct.length > 0) {
        console.log('\n📦 Direct MP4 URLs:');
        mp4Direct.forEach(u => console.log(`  ${u}`));
      }

      console.log(`\n=== TOTAL: ${unique.length} unique video URLs ===`);

      ws.close();
      process.exit(0);
    }, waitSeconds * 1000);
  });

  ws.on('message', (raw) => {
    const msg = JSON.parse(raw.toString());

    // Network.requestWillBeSent 이벤트에서 비디오 URL 캡처
    if (msg.method === 'Network.requestWillBeSent') {
      const url = msg.params?.request?.url || '';
      if (isVideoUrl(url)) {
        console.log(`FOUND: ${url.substring(0, 200)}`);
        videoUrls.push(url);
      }
    }

    // Network.responseReceived에서도 확인
    if (msg.method === 'Network.responseReceived') {
      const url = msg.params?.response?.url || '';
      if (isVideoUrl(url) && !videoUrls.includes(url)) {
        videoUrls.push(url);
      }
    }
  });

  ws.on('error', e => {
    console.error(`WebSocket error: ${e.message}`);
    process.exit(1);
  });
}
