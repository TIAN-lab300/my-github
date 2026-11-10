export class ApiError extends Error {
    constructor(public status: number, message: string) { super(message); }
}
export async function api<T = any>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const form = body instanceof FormData;
    const response = await fetch('/api/v1' + path, { method, credentials: 'same-origin', headers: { ...(!form && body ? { 'Content-Type': 'application/json' } : {}), ...(method === 'POST' ? { 'Idempotency-Key': crypto.randomUUID() } : {}) }, body: body ? (form ? body : JSON.stringify(body)) : undefined });
    const data = await response.json().catch(() => ({ message: '服务响应格式错误' }));
    if (!response.ok) {
        if (response.status === 401)
            window.dispatchEvent(new Event('session-expired'));
        const detail = data.message || data.detail;
        throw new ApiError(response.status, typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x: any) => x.msg).join('；') : '操作失败');
    }
    return data;
}
export function parse<T = any>(value: any): T { return typeof value === 'string' ? JSON.parse(value) : value; }
export type User = {
    id: string;
    username: string;
    name: string;
    role: 'admin' | 'teacher' | 'student';
    must_change: number;
};
