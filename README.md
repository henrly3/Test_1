# Test_1 — SATA SSD Test Program

Linux용 SATA SSD 테스트 프로그램입니다. Python 3.9+ 표준 라이브러리만 사용하며 외부 의존성이 없습니다.

- **ATA 명령**: SG_IO + SCSI ATA PASS-THROUGH(16)으로 `IDENTIFY DEVICE`, `SMART READ DATA/THRESHOLDS`, `SMART RETURN STATUS`를 직접 전송 (libata `/dev/sdX`, SAT 지원 USB-SATA 브리지)
- **I/O**: `O_DIRECT` + 페이지 정렬 버퍼로 페이지 캐시를 우회

## 테스트 항목

| 테스트 | 쓰기 | 내용 |
|---|---|---|
| `identify` | | 모델/시리얼/펌웨어, 용량, 섹터 크기, SATA 링크 속도(1.5/3/6 Gb/s), NCQ, TRIM(DRAT/RZAT) 지원 |
| `smart` | | SMART 속성·임계값, 전체 Health. 임계값 이하 → FAIL, 재할당/Pending/Uncorrectable/CRC 에러 raw 값 경고 |
| `read_scan` | | 영역 전체 읽기, 읽기 에러와 느린 블록(`--slow-ms`) 검출 |
| `seq_read` / `seq_write` | / ✔ | 순차 처리량(MB/s), 지연시간 분포 |
| `rand_read` / `rand_write` | / ✔ | 4K 랜덤 IOPS, 지연시간 p50/p99/p99.9/max, `--qd`로 큐 깊이(스레드 수) 지정 |
| `verify` | ✔ | 0x00 / 0xFF / 0xAA55 / 랜덤 패턴 쓰기 → 읽기 비교. 랜덤 패턴은 4KiB마다 주소·시드 스탬프를 넣어 비트 오류뿐 아니라 **잘못된 주소에 쓰기(misdirected write)·이전 데이터 잔존**도 검출 |
| `trim` | ✔ | 데이터 기록 후 `BLKDISCARD`, 이후 읽기 결과(0 / 이전 데이터 / 기타) 보고. RZAT를 지원한다고 하면서 0이 아니면 FAIL |

## 사용법

```bash
# 읽기 전용 기본 세트 (identify, smart, read_scan, seq_read, rand_read)
sudo python3 -m ssd_test /dev/sdb

# 전체 세트 (쓰기 포함 — 데이터 삭제됨!)
sudo python3 -m ssd_test /dev/sdb --destructive

# 특정 테스트, 영역/옵션 지정, JSON 리포트
sudo python3 -m ssd_test /dev/sdb --destructive -t verify,trim --offset 10G --span 4G
sudo python3 -m ssd_test /dev/sdb --destructive -t rand_write,rand_read --qd 32 --duration 30
sudo python3 -m ssd_test /dev/sdb --destructive --full-span --loops 3 --json report.json

# 합격 기준 (미달 시 FAIL)
sudo python3 -m ssd_test /dev/sdb --destructive --min-seq-read 500 --min-rand-read-iops 50000

# SSD 없이 이미지 파일로 동작 확인
truncate -s 1G disk.img && python3 -m ssd_test disk.img --destructive -y
```

`pip install .` 하면 `ssd_test` 명령으로도 실행할 수 있습니다. 전체 옵션은 `--help` 참고.

## 안전장치

- 쓰기 테스트는 `--destructive` 없이는 실행되지 않습니다.
- 디바이스 또는 그 파티션이 마운트되어 있으면 쓰기를 거부합니다.
- 실행 전 디바이스 경로를 직접 입력해야 진행됩니다 (`-y`로 생략 가능).
- 기본 테스트 영역은 앞쪽 1 GiB이며, 전체는 `--full-span`.

## 종료 코드

`0` 전체 PASS, `1` FAIL 있음, `2` 사용법/디바이스 오류, `130` 중단(Ctrl+C).

## 참고 / 한계

- 성능 수치는 Python 스레드 기반이라 fio 대비 높은 QD에서 낮게 나올 수 있습니다. 절대값 벤치마크보다는 동일 조건 비교·회귀 검출용으로 적합합니다.
- SG_IO(ATA 명령)는 root 권한이 필요하고, NVMe 및 SAT 미지원 브리지에서는 `identify`/`smart`가 SKIP됩니다.

## 개발

```bash
pytest   # 이미지 파일 기반 단위 테스트, SSD 불필요
```
