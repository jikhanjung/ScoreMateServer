import { NextRequest, NextResponse } from 'next/server';

export async function PUT(request: NextRequest) {
  try {
    const url = request.nextUrl.searchParams.get('url');
    if (!url) {
      return NextResponse.json({ error: 'URL parameter is required' }, { status: 400 });
    }

    // Get the file data from the request
    const fileData = await request.arrayBuffer();
    
    // Extract headers from the request
    const contentType = request.headers.get('content-type') || 'application/octet-stream';
    
    // Forward the request to MinIO
    const response = await fetch(url, {
      method: 'PUT',
      body: fileData,
      headers: {
        'Content-Type': contentType,
      },
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
    }

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Upload proxy error:', error);
    return NextResponse.json(
      { error: error.message || 'Upload failed' },
      { status: 500 }
    );
  }
}