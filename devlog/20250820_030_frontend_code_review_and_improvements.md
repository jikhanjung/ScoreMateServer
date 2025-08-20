# 프론트엔드 코드 리뷰 및 개선 제안

**날짜**: 2025년 8월 20일
**작성자**: Gemini
**문서 목적**: 현재까지 개발된 프론트엔드 코드 베이스 전체에 대한 리뷰 및 향후 유지보수성과 확장성을 높이기 위한 개선 방안 제안

---

## 1. 종합 평가

현재 프론트엔드 코드 베이스는 **매우 훌륭한 수준**입니다. Next.js 15, TypeScript, Tailwind CSS 등 최신 기술 스택을 효과적으로 활용하고 있으며, 프로젝트 구조가 논리적이고 초기 설정이 견고합니다.

특히 아래와 같은 강점들이 돋보입니다.

- **견고한 아키텍처**: `lib/api.ts`를 중심으로 한 API 클라이언트, `AuthContext`를 통한 전역 인증 관리, `providers.tsx`를 통한 설정 분리 등 확장성을 고려한 설계가 적용되어 있습니다.
- **컴포넌트 기반 설계**: 재사용 가능한 UI 컴포넌트(`components/ui`)가 잘 분리되어 있어 일관성 있는 UI 개발이 가능합니다.
- **안정적인 데이터 관리**: `TanStack Query`를 활용하여 서버 상태(데이터 페칭, 캐싱, 동기화)를 효과적으로 관리하고 있습니다.
- **포괄적인 E2E 테스트**: Playwright를 이용한 엔드투엔드 테스트는 코드의 안정성을 크게 높여줍니다.

아래 제안들은 현재의 훌륭한 코드 베이스를 한 단계 더 발전시켜, 앞으로 기능이 더 복잡해지더라도 **유지보수와 확장을 용이하게 만드는 것**에 초점을 맞춥니다.

---

## 2. 개선 제안

### 가. 컴포넌트 및 상태 관리 로직 분리 (Custom Hooks 도입)

- **현재 상황**:
  - `app/scores/page.tsx`, `app/upload/page.tsx` 등의 페이지 컴포넌트가 데이터 페칭, UI 상태(`useState`), 비즈니스 로직(`useEffect`), 렌더링(JSX) 등 너무 많은 책임을 가지고 있습니다.
  - 이로 인해 컴포넌트의 크기가 커지고, 로직을 재사용하기 어렵습니다.

- **개선 제안**:
  - **Custom Hook**을 도입하여 데이터와 비즈니스 로직을 UI로부터 분리합니다.
  - 예를 들어, `useScores` 훅은 악보 목록과 관련된 모든 로직(API 호출, 페이징, 정렬, 검색 상태)을 포함하고, 페이지 컴포넌트는 이 훅을 호출하여 필요한 상태와 함수만 받아와 렌더링에 집중합니다.

- **기대 효과**:
  - **관심사의 분리(SoC)**: 컴포넌트는 순수하게 UI 렌더링에만 집중할 수 있습니다.
  - **재사용성 증가**: 동일한 데이터 로직이 다른 컴포넌트에서도 필요할 경우 훅을 재사용할 수 있습니다.
  - **가독성 및 테스트 용이성**: 코드가 간결해지고, 훅을 독립적으로 테스트하기 쉬워집니다.

- **예시: `useScores` 훅**
  ```typescript
  // /frontend/hooks/useScores.ts (신규 생성)
  import { useState, useEffect } from 'react';
  import { apiClient } from '@/lib/api';
  import { Score } from '@/types/api';

  export function useScores() {
    const [scores, setScores] = useState<Score[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    // ... 기타 상태 및 로직 ...

    useEffect(() => {
      // API 호출 로직
    }, [currentPage, /* ... */]);

    return { scores, isLoading, error, currentPage, setCurrentPage, /* ... */ };
  }

  // /frontend/app/scores/page.tsx (리팩토링 후)
  'use client';
  import { useScores } from '@/hooks/useScores';

  export default function ScoresPage() {
    const { scores, isLoading, error, /* ... */ } = useScores();

    if (isLoading) return <LoadingSpinner />;
    if (error) return <ErrorMessage message={error} />;

    return (
      // JSX 렌더링 부분
    );
  }
  ```

### 나. 폼(Form) 처리 방식 개선

- **현재 상황**:
  - `login/page.tsx`, `register/page.tsx`에서 `useState`를 사용하여 폼 상태를 수동으로 관리하고, 유효성 검사 로직을 직접 작성하고 있습니다.
  - 코드가 길어지고, 복잡한 유효성 검사나 에러 처리가 추가될수록 유지보수가 어려워집니다.

- **개선 제안**:
  - **`react-hook-form` 라이브러리**를 도입하여 폼 상태 관리, 유효성 검사, 제출 로직을 표준화하고 간소화합니다.
  - 이 라이브러리는 비제어 컴포넌트(uncontrolled components) 방식으로 작동하여 불필요한 리렌더링을 줄여 성능에도 이점이 있습니다.

- **기대 효과**:
  - **코드 간소화**: 보일러플레이트 코드가 대폭 감소합니다.
  - **성능 향상**: 입력할 때마다 리렌더링이 발생하지 않습니다.
  - **강력한 유효성 검사**: 내장된 유효성 검사 규칙 및 외부 라이브러리(e.g., `zod`)와의 연동이 쉽습니다.

### 다. API 레이어 및 타입 안정성 강화

- **현재 상황**:
  - `dashboard/page.tsx`에서 `dashboardData.latest_content.scores`의 타입이 `any[]`로 되어 있어 타입스크립트의 이점을 제대로 활용하지 못하고 있습니다.
  - `types/api.ts`에 정의된 타입들이 전반적으로 훌륭하지만, 일부 세부적인 타입이 누락되어 있습니다.

- **개선 제안**:
  - `types/api.ts`에 `ScoreSummary`와 같은 요약 타입을 추가하여 `any` 사용을 제거합니다.
  - API 클라이언트(`lib/api.ts`)의 `get` 요청에 제네릭을 명시적으로 사용하여, 응답 데이터의 타입을 컴파일 타임에 확인할 수 있도록 합니다.

- **예시: 타입 정의 강화**
  ```typescript
  // /frontend/types/api.ts (수정)
  export interface ScoreSummary {
    id: number;
    title: string;
    composer?: string;
    created_at: string;
    pages?: number;
  }

  export interface DashboardLatestContent {
    scores: ScoreSummary[]; // any[] 대신 ScoreSummary[] 사용
    setlists: any[]; // SetlistSummary 타입도 추가하면 좋음
  }
  ```

### 라. 코드 중복 제거 및 일관성 확보

- **현재 상황**:
  - `formatFileSize`, `formatDate`와 같은 유틸리티 함수가 `lib/utils.ts`에 정의되어 있음에도 불구하고, `dashboard/page.tsx`나 `scores/page.tsx` 내부에 중복으로 정의되어 사용되고 있습니다.

- **개선 제안**:
  - 컴포넌트 내부에 정의된 유틸리티 함수들을 모두 제거하고, `lib/utils.ts`에 있는 함수를 `import`하여 사용하도록 통일합니다.
  - **DRY(Don't Repeat Yourself)** 원칙을 준수하여 코드의 일관성을 높이고 유지보수를 용이하게 합니다.

---

## 3. 실행 계획 제안 (Action Plan)

아래 순서로 개선 작업을 진행하는 것을 권장합니다.

1.  **(즉시) 유틸리티 함수 통합**: 가장 간단하고 빠르게 효과를 볼 수 있는 작업입니다. 컴포넌트 내 중복 함수를 제거하고 `lib/utils.ts`를 사용하도록 수정합니다.
2.  **(단기) 폼 처리 라이브러리 도입**: `react-hook-form`을 `login`, `register` 페이지에 적용하여 폼 관련 코드를 리팩토링합니다.
3.  **(단기) Custom Hook 도입**: `scores`, `dashboard`, `upload` 페이지의 로직을 각각 `useScores`, `useDashboardData`, `useFileUpload` 훅으로 분리하여 컴포넌트를 간소화합니다.
4.  **(지속적) 타입 정의 강화**: `any` 타입을 사용하는 부분을 찾아 구체적인 타입으로 교체하고, 새로운 API 연동 시 타입을 우선적으로 정의합니다.

## 4. 결론

현재 프론트엔드 코드는 매우 잘 짜여진 상태이며, 제안된 개선안들은 이미 구축된 튼튼한 기반 위에서 코드의 장기적인 건강성을 확보하기 위함입니다. 특히 **Custom Hook의 도입**은 향후 애플리케이션이 복잡해질 때를 대비하여 **확장성과 유지보수성을 크게 향상**시킬 수 있는 가장 중요한 개선 사항입니다.
