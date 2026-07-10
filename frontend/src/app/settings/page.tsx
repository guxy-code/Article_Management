"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2, Check } from "lucide-react";
import { getMe, changePassword, updateProfile } from "@/lib/api";
import { getUser, setAuth } from "@/lib/auth";

export default function SettingsPage() {
  const [userInfo, setUserInfo] = useState<{ id: string; username: string; email: string | null; created_at: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Profile form
  const [profileUsername, setProfileUsername] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileMsg, setProfileMsg] = useState("");
  const [profileError, setProfileError] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pwdMsg, setPwdMsg] = useState("");
  const [pwdError, setPwdError] = useState("");
  const [isSavingPwd, setIsSavingPwd] = useState(false);

  useEffect(() => {
    getMe()
      .then((data) => {
        setUserInfo(data);
        setProfileUsername(data.username);
        setProfileEmail(data.email || "");
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError("");
    setProfileMsg("");

    if (!profileUsername.trim()) {
      setProfileError("用户名不能为空");
      return;
    }

    setIsSavingProfile(true);
    try {
      const result = await updateProfile(profileUsername.trim(), profileEmail.trim() || undefined);
      setAuth(result.token, result.user);
      setProfileMsg("资料更新成功");
      setUserInfo((prev) => prev ? { ...prev, username: result.user.username, email: profileEmail || null } : null);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "更新失败");
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdError("");
    setPwdMsg("");

    if (!currentPassword) {
      setPwdError("请输入当前密码");
      return;
    }

    const pwdError = validatePasswordStrength(newPassword);
    if (pwdError) {
      setPwdError(pwdError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdError("两次新密码不一致");
      return;
    }

    setIsSavingPwd(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPwdMsg("密码修改成功");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPwdError(err instanceof Error ? err.message : "修改失败");
    } finally {
      setIsSavingPwd(false);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="px-6 py-5 max-w-2xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
          <h1 className="text-xl font-semibold tracking-tight mb-5">Settings</h1>

          {/* Account Info */}
          <div className="p-5 rounded-[14px] border border-border bg-white card-shadow mb-4">
            <h2 className="text-sm font-medium mb-4">Account Info</h2>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[12px] text-muted-foreground">Account ID</span>
                <span className="text-[12px] font-mono text-foreground break-all">{userInfo?.id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[12px] text-muted-foreground">Member since</span>
                <span className="text-[12px] text-foreground">{userInfo?.created_at.split("T")[0]}</span>
              </div>
            </div>
          </div>

          {/* Edit Profile */}
          <div className="p-5 rounded-[14px] border border-border bg-white card-shadow mb-4">
            <h2 className="text-sm font-medium mb-4">Edit Profile</h2>
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div>
                <label className="text-[13px] font-medium text-foreground mb-1.5 block">Username</label>
                <input
                  type="text"
                  value={profileUsername}
                  onChange={(e) => setProfileUsername(e.target.value)}
                  className="w-full h-10 px-3 rounded-[10px] border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
                />
              </div>
              <div>
                <label className="text-[13px] font-medium text-foreground mb-1.5 block">Email</label>
                <input
                  type="email"
                  value={profileEmail}
                  onChange={(e) => setProfileEmail(e.target.value)}
                  placeholder="optional"
                  className="w-full h-10 px-3 rounded-[10px] border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
                />
              </div>
              {profileError && (
                <p className="text-[13px] text-destructive bg-destructive/5 px-3 py-2 rounded-[8px]">{profileError}</p>
              )}
              {profileMsg && (
                <p className="text-[13px] text-emerald-600 bg-emerald-50 px-3 py-2 rounded-[8px] flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />{profileMsg}
                </p>
              )}
              <button
                type="submit"
                disabled={isSavingProfile || !profileUsername.trim()}
                className="h-10 px-5 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                {isSavingProfile && <Loader2 className="w-4 h-4 animate-spin" />}
                Save Profile
              </button>
            </form>
          </div>

          {/* Change Password */}
          <div className="p-5 rounded-[14px] border border-border bg-white card-shadow">
            <h2 className="text-sm font-medium mb-4">Change Password</h2>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label className="text-[13px] font-medium text-foreground mb-1.5 block">Current Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter current password"
                    autoComplete="current-password"
                    className="w-full h-10 px-3 pr-10 rounded-[10px] border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="text-[13px] font-medium text-foreground mb-1.5 block">New Password</label>
                <input
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少6位，含大小写字母/数字/特殊字符两种"
                  autoComplete="new-password"
                  className="w-full h-10 px-3 rounded-[10px] border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
                />
              </div>
              <div>
                <label className="text-[13px] font-medium text-foreground mb-1.5 block">Confirm New Password</label>
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter new password"
                  autoComplete="new-password"
                  className="w-full h-10 px-3 rounded-[10px] border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all"
                />
              </div>
              {pwdError && (
                <p className="text-[13px] text-destructive bg-destructive/5 px-3 py-2 rounded-[8px]">{pwdError}</p>
              )}
              {pwdMsg && (
                <p className="text-[13px] text-emerald-600 bg-emerald-50 px-3 py-2 rounded-[8px] flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />{pwdMsg}
                </p>
              )}
              <button
                type="submit"
                disabled={isSavingPwd || !currentPassword || !newPassword || !confirmPassword}
                className="h-10 px-5 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                {isSavingPwd && <Loader2 className="w-4 h-4 animate-spin" />}
                Update Password
              </button>
            </form>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function validatePasswordStrength(password: string): string | null {
  if (password.length < 6) return "密码至少 6 位";
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecial = /[^a-zA-Z0-9]/.test(password);
  const count = [hasUpper, hasLower, hasDigit, hasSpecial].filter(Boolean).length;
  if (count < 2) return "密码需包含大写字母、小写字母、数字、特殊字符中的至少两种";
  return null;
}
