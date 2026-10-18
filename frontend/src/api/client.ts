export async function api<T = any>(path: string, payload?: unknown): Promise<T> {
  const options: RequestInit = {
    ...(payload === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }),
  };

  const response = await fetch(path, options);
  const data = await response.json();

  if (!response.ok) {
    const error = new Error(data.error || 'Request failed') as Error & { status?: number };
    error.status = response.status;
    throw error;
  }

  return data as T;
}
