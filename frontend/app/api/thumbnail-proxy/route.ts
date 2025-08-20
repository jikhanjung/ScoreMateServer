import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const thumbnailKey = request.nextUrl.searchParams.get('key');
    
    if (!thumbnailKey) {
      return NextResponse.json({ error: 'Key parameter is required' }, { status: 400 });
    }

    // Use backend API to get presigned URL, then fetch the image
    const backendUrl = `http://localhost:8000/api/v1/files/thumbnail/${encodeURIComponent(thumbnailKey)}`;
    
    const response = await fetch(backendUrl, {
      method: 'GET',
    });

    if (!response.ok) {
      console.error(`Backend fetch failed: ${response.status} ${response.statusText}`);
      return NextResponse.json({ error: 'Failed to fetch thumbnail' }, { status: response.status });
    }

    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get('content-type') || 'image/jpeg';

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Thumbnail proxy error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}