/**
 * 前端认证状态管理
 * 负责 JWT token 和用户信息的存储、读取、过期检测。
 */

const TOKEN_KEY = "papermind_token";
const USER_KEY = "papermind_user";

export interface AuthUser {
  id: string;
  username: string;
}

/** 登录成功后存储 token 和用户信息 */
export function setAuth(token: string, user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** 获取当前 token */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** 获取当前用户信息 */
export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** 检查 token 是否存在且未过期 */
export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    // 解析 JWT payload（不验签，只看 exp）
    const payload = JSON.parse(atob(token.split(".")[1]));
    const expMs = payload.exp * 1000;
    return Date.now() < expMs;
  } catch {
    return false;
  }
}

/** 退出登录：清除本地存储并跳转登录页 */
export function logout(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = "/login";
}
