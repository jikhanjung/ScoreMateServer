# Backend API Endpoints Required

## Missing Endpoints for Phase 4 Implementation

### 1. Bulk Metadata Update Endpoint

**Endpoint**: `POST /api/v1/scores/bulk_metadata/`

**Purpose**: Update metadata fields for multiple scores at once

**Request Body**:
```json
{
  "score_ids": [1, 2, 3, 4],
  "metadata": {
    "composer": "Johann Sebastian Bach",
    "genre": "클래식", 
    "difficulty": 4,
    "description": "Updated description"
  }
}
```

**Response**:
```json
{
  "success": true,
  "updated_scores": 4,
  "total_scores": 4,
  "message": "Successfully updated metadata for 4 scores"
}
```

**Implementation Notes**:
- Should only update non-empty fields in metadata
- Should validate that all score_ids belong to the requesting user
- Should return appropriate error messages for validation failures
- Should be added to `backend/scores/views.py` in the `ScoreViewSet` class

**Frontend Implementation**: ✅ Complete
- API method: `scoreApi.bulkUpdateMetadata()` in `lib/api.ts`
- Hook integration: `bulkUpdateMetadata()` in `hooks/useScores.ts` 
- UI component: Bulk metadata edit modal in `components/scores/BulkActions.tsx`
- Page integration: Handler in `app/scores/page.tsx`