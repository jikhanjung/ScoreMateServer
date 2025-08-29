# ScoreMate API Documentation (v1)

**작성일**: 2025년 8월 21일  
**작성자**: Gemini  
**문서 버전**: 1.0

## 1. 개요

이 문서는 ScoreMate 프로젝트의 v1 API에 대한 명세를 정리합니다. 모든 API의 기본 경로는 `/api/v1/` 입니다.

---

## 2. 인증 (Authentication)

### **`POST /auth/register/`**

*   **설명**: 새로운 사용자를 등록합니다.
*   **Input (Request Body)**:
    *   `email` (string, required): 사용자 이메일 (로그인 시 ID로 사용)
    *   `username` (string, required): 사용자 이름
    *   `password` (string, required): 비밀번호
    *   `password_confirm` (string, required): 비밀번호 확인
    *   `plan` (string, optional): 요금제 (기본값: `solo`)
*   **Output (Response Body)**:
    ```json
    {
        "user": { ...UserProfileSerializer ... },
        "tokens": {
            "refresh": "<refresh_token>",
            "access": "<access_token>"
        }
    }
    ```

### **`POST /auth/login/`**

*   **설명**: 이메일과 비밀번호로 로그인하여 JWT 토큰을 발급받습니다.
*   **Input (Request Body)**:
    *   `email` (string, required): 사용자 이메일
    *   `password` (string, required): 비밀번호
*   **Output (Response Body)**:
    ```json
    {
        "user": { ...UserProfileSerializer ... },
        "tokens": {
            "refresh": "<refresh_token>",
            "access": "<access_token>"
        }
    }
    ```

### **`POST /auth/token/refresh/`**

*   **설명**: Refresh 토큰을 사용하여 새로운 Access 토큰을 발급받습니다.
*   **Input (Request Body)**:
    *   `refresh` (string, required): Refresh 토큰
*   **Output (Response Body)**:
    ```json
    {
        "access": "<new_access_token>"
    }
    ```

### **`POST /auth/token/verify/`**

*   **설명**: Access 토큰의 유효성을 검증합니다.
*   **Input (Request Body)**:
    *   `token` (string, required): Access 토큰
*   **Output (Response Body)**: (성공 시) `200 OK` 와 빈 Body, (실패 시) `401 Unauthorized`

---

## 3. 사용자 및 대시보드

### **`GET /user/profile/`**

*   **설명**: 현재 로그인된 사용자의 프로필 정보를 조회합니다.
*   **Input**: 없음 (Header에 Access Token 필요)
*   **Output (Response Body - UserProfileSerializer)**:
    *   `id`, `email`, `username`, `plan`
    *   `total_quota_mb`, `used_quota_mb`, `available_quota_mb`, `quota_usage_percentage`
    *   `referral_code`, `date_joined`, `last_login`

### **`PUT / PATCH /user/profile/`**

*   **설명**: 사용자 프로필 정보를 수정합니다. (현재는 `username`, `plan`만 수정 가능)
*   **Input (Request Body)**:
    *   `username` (string, optional)
    *   `plan` (string, optional)
*   **Output (Response Body)**: 수정된 `UserProfileSerializer` 정보

### **`GET /dashboard/`**

*   **설명**: 대시보드에 필요한 요약 정보를 조회합니다.
*   **Input**: 없음
*   **Output (Response Body)**: 사용자 정보, 악보/세트리스트 개수, 용량 정보, 최근 활동, 최신 콘텐츠 목록 등 종합 데이터

---

## 4. 악보 (Scores)

### **`GET /scores/`**

*   **설명**: 사용자의 모든 악보 목록을 조회합니다. 다양한 필터링 및 정렬 옵션을 지원합니다.
*   **Input (Query Parameters - ScoreFilter)**:
    *   `search` (string): 제목, 작곡가, 악기 편성에서 Full-text 검색
    *   `title` (string): 제목 포함 검색
    *   `composer` (string): 작곡가 포함 검색
    *   `tags` (string): 쉼표로 구분된 태그 목록 (AND 조건)
    *   `has_tags` (boolean): 태그 존재 여부
    *   `size_mb_min` / `size_mb_max` (number): 파일 크기(MB) 범위
    *   `pages_min` / `pages_max` (number): 페이지 수 범위
    *   `has_pages` (boolean): 페이지 수 정보 존재 여부
    *   `created_after` / `created_before` (datetime): 생성일 범위
    *   `has_thumbnail` (boolean): 썸네일 존재 여부
    *   `ordering` (string): 정렬 필드 (`title`, `composer`, `created_at`, `updated_at`, `size_mb`, `pages` 등. `-` 접두사로 내림차순)
*   **Output (Response Body)**: `ScoreListSerializer`의 배열

### **`POST /scores/`**

*   **설명**: 새 악보 정보를 생성합니다. (파일 업로드 완료 후 호출)
*   **Input (Request Body - ScoreCreateSerializer)**:
    *   `title` (string, required)
    *   `s3_key` (string, required): 업로드된 파일의 S3 경로
    *   `size_bytes` (integer, required): 파일 크기
    *   `mime` (string, required): 파일 MIME 타입
    *   `composer` (string, optional)
    *   `instrumentation` (string, optional)
    *   `tags` (array of strings, optional)
    *   `note` (string, optional)
    *   `content_hash` (string, optional)
*   **Output (Response Body)**: 생성된 `ScoreSerializer` 정보

### **`GET /scores/{id}/`**

*   **설명**: 특정 악보의 상세 정보를 조회합니다.
*   **Input**: 없음
*   **Output (Response Body - ScoreSerializer)**: `id`, `title`, `composer`, `tags`, `size_mb`, `pages` 등 모든 필드

### **`PUT / PATCH /scores/{id}/`**

*   **설명**: 특정 악보의 정보를 수정합니다.
*   **Input (Request Body)**: `ScoreSerializer`의 수정 가능한 필드들 (`title`, `composer`, `tags` 등)
*   **Output (Response Body)**: 수정된 `ScoreSerializer` 정보

### **`DELETE /scores/{id}/`**

*   **설명**: 특정 악보를 삭제합니다.
*   **Input**: 없음
*   **Output**: `204 No Content`

### **`POST /scores/bulk_tag/`**

*   **설명**: 여러 악보에 대해 태그를 일괄 추가하거나 제거합니다.
*   **Input (Request Body)**:
    *   `score_ids` (array of integers, required)
    *   `add_tags` (array of strings, optional)
    *   `remove_tags` (array of strings, optional)
*   **Output (Response Body)**:
    ```json
    {
        "message": "Updated tags for 5 scores",
        "updated_scores": 5,
        "total_scores": 5
    }
    ```

---

## 5. 세트리스트 (Setlists)

(악보 API와 유사한 표준 RESTful API 구조를 가집니다)

### **`GET /setlists/`**: 모든 세트리스트 목록 조회
*   **Output**: `SetlistListSerializer`의 배열 (`id`, `title`, `item_count` 등)

### **`POST /setlists/`**: 새 세트리스트 생성
*   **Input**: `title` (string), `description` (string, optional)
*   **Output**: 생성된 `SetlistCreateUpdateSerializer` 정보

### **`GET /setlists/{id}/`**: 특정 세트리스트 상세 정보 조회 (포함된 악보 목록 포함)
*   **Output**: `SetlistSerializer` 정보

### **`PUT / PATCH /setlists/{id}/`**: 세트리스트 정보 수정
*   **Input**: `title` (string), `description` (string, optional)
*   **Output**: 수정된 `SetlistCreateUpdateSerializer` 정보

### **`DELETE /setlists/{id}/`**: 세트리스트 삭제

### **`POST /setlists/{id}/add_items/`**: 세트리스트에 여러 악보 추가
*   **Input**: `score_ids` (array of integers, required)
*   **Output**: 추가된 아이템 정보

### **`DELETE /setlists/{id}/items/{item_id}/`**: 세트리스트에서 특정 악보 제거

### **`POST /setlists/{id}/duplicate/`**: 세트리스트 복제

---

## 6. 파일 (Files)

### **`POST /files/upload-url/`**

*   **설명**: 파일 업로드를 위한 1회용 Presigned URL을 생성합니다.
*   **Input (Request Body)**:
    *   `filename` (string, optional)
    *   `size_bytes` (integer, required)
    *   `mime_type` (string, required)
*   **Output (Response Body)**: `upload_id`, `upload_url`, `s3_key` 등

### **`GET /files/download/{score_id}/`**

*   **설명**: 파일 다운로드를 위한 1회용 Presigned URL을 생성합니다.
*   **Input (Query Parameters)**:
    *   `file_type` (string, optional): `original` 또는 `thumbnail` (기본값: `original`)
*   **Output (Response Body)**: `download_url` 등

### **`POST /files/upload-confirm/`**

*   **설명**: 파일 업로드 완료 후, 서버에 이를 알리고 악보 생성을 트리거합니다.
*   **Input (Request Body)**:
    *   `upload_id` (string, required)
    *   `title` (string, required)
    *   `composer` (string, optional)
    *   `tags` (array of strings, optional)
*   **Output (Response Body)**: `score_id`, `quota_used_mb` 등

---

## 7. ⚠️ 요구되는 API (미구현)

프론트엔드의 Phase 4 기능 구현을 위해 다음 백엔드 API의 개발이 필요합니다.

### **`POST /scores/bulk_metadata/`**

*   **설명**: 여러 악보의 메타데이터(작곡가, 장르 등)를 한 번에 수정합니다.
*   **Input (Request Body)**:
    ```json
    {
      "score_ids": [1, 2, 3],
      "metadata": {
        "composer": "Johann Sebastian Bach",
        "genre": "클래식", 
        "difficulty": 4
      }
    }
    ```
*   **Output (Response Body)**:
    ```json
    {
      "success": true,
      "updated_scores": 3
    }
    ```
