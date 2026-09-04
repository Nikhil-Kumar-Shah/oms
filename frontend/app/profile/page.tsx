'use client';

/**
 * User Profile Workspace (/profile)
 * Professional, clean profile presentation for authenticated operators and leadership.
 * Displays canonical user identity, contact details, operational specialization,
 * availability status, self-service profile updates, and secure password changes.
 */

import React, { useState, useEffect } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { PasswordRequirements } from '@/components/ui/PasswordRequirements';
import { useAuth } from '@/hooks/useAuth';
import { authApi, profileApi, ApiException } from '@/lib/api';
import {
  UserProfile,
  UserOperationalProfile,
  UserAvailability,
  CanonicalRole,
} from '@/types/user';
import { formatAuditDateTime } from '@/lib/utils';
import {
  User as UserIcon,
  Layers,
  Clock,
  Briefcase,
  Award,
  Edit3,
  CheckCircle2,
  Lock,
  FileText,
  Activity,
  Phone,
  Mail,
  Sparkles,
} from 'lucide-react';

const AVAILABILITY_CONFIG: Record<
  UserAvailability,
  { label: string; color: string }
> = {
  AVAILABLE: {
    label: 'Available',
    color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300',
  },
  BUSY: {
    label: 'Busy / On Duty',
    color: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300',
  },
  ON_LEAVE: {
    label: 'On Leave',
    color: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300',
  },
  EMERGENCY_ONLY: {
    label: 'Emergency Only',
    color: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300',
  },
};

export default function ProfilePage() {
  const { user: authUser, refreshUser } = useAuth();

  const [profile, setProfile] = useState<UserOperationalProfile | null>(null);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit Profile Modal
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [editLoading, setEditLoading] = useState<boolean>(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    phone_number: '',
    specialization: '',
    operational_capability: '',
    certifications_text: '',
    availability: 'AVAILABLE' as UserAvailability,
    profile_notes: '',
  });

  // Change Password Modal
  const [isPasswordOpen, setIsPasswordOpen] = useState<boolean>(false);
  const [passwordLoading, setPasswordLoading] = useState<boolean>(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    let active = true;

    Promise.all([
      authApi.getMe(),
      profileApi.getMyProfile().catch(() => null),
    ])
      .then(([meRes, opProfile]) => {
        if (active) {
          setCurrentUser(meRes);
          setProfile(opProfile);
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err instanceof ApiException ? err.message : 'Failed to load profile details.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const activeUser = currentUser || authUser;
  const firstRole = activeUser?.roles?.[0];
  const primaryRole: CanonicalRole =
    typeof firstRole === 'string'
      ? (firstRole as CanonicalRole)
      : (firstRole && 'name' in firstRole ? firstRole.name : 'VOLUNTEER');
  const availabilityKey = (profile?.availability as UserAvailability) || 'AVAILABLE';
  const availabilityMeta = AVAILABILITY_CONFIG[availabilityKey] || AVAILABILITY_CONFIG.AVAILABLE;

  const openEditModal = () => {
    setEditForm({
      phone_number: profile?.phone_number || '',
      specialization: profile?.specialization || '',
      operational_capability: profile?.operational_capability || '',
      certifications_text: profile?.certifications?.join(', ') || '',
      availability: (profile?.availability as UserAvailability) || 'AVAILABLE',
      profile_notes: profile?.profile_notes || '',
    });
    setEditError(null);
    setIsEditOpen(true);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditLoading(true);
    setEditError(null);

    const certs = editForm.certifications_text
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);

    try {
      const updated = await profileApi.updateMyProfile({
        phone_number: editForm.phone_number.trim() || undefined,
        specialization: editForm.specialization.trim() || undefined,
        operational_capability: editForm.operational_capability.trim() || undefined,
        certifications: certs,
        availability: editForm.availability,
        profile_notes: editForm.profile_notes.trim() || undefined,
      });

      setProfile(updated);
      setSuccessMsg('Profile updated successfully.');
      setIsEditOpen(false);
      await refreshUser();
    } catch (err) {
      if (err instanceof ApiException) {
        setEditError(err.message);
      } else if (err instanceof Error) {
        setEditError(err.message);
      }
    } finally {
      setEditLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordForm.current_password) {
      setPasswordError('Please enter your current password.');
      return;
    }
    if (passwordForm.new_password.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    setPasswordLoading(true);
    setPasswordError(null);

    try {
      await authApi.changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setSuccessMsg('Password changed successfully.');
      setIsPasswordOpen(false);
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      if (err instanceof ApiException) {
        setPasswordError(err.message);
      } else if (err instanceof Error) {
        setPasswordError(err.message);
      }
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* Profile Header Card */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-purple-950/25 via-indigo-950/20 to-zinc-900 border border-purple-200/50 dark:border-purple-800/40 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-indigo-500/20 shrink-0">
              {activeUser?.full_name?.charAt(0).toUpperCase() || activeUser?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                  {activeUser?.full_name || activeUser?.username}
                </h1>
                <Badge role={primaryRole} size="sm" />
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${availabilityMeta.color}`}
                >
                  <Activity className="w-3 h-3 mr-1" />
                  {availabilityMeta.label}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
                <span className="font-mono text-indigo-600 dark:text-indigo-400 font-semibold">
                  @{activeUser?.username}
                </span>
                {activeUser?.email && <span>• {activeUser.email}</span>}
                {activeUser?.verticals && activeUser.verticals.length > 0 && (
                  <span>
                    • Vertical:{' '}
                    <span className="font-medium text-zinc-700 dark:text-zinc-300">
                      {activeUser.verticals.find((v) => v.is_primary)?.name || activeUser.verticals[0].name}
                    </span>
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 self-end md:self-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={openEditModal}
              leftIcon={<Edit3 className="w-3.5 h-3.5" />}
            >
              Edit Profile
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setPasswordError(null);
                setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
                setIsPasswordOpen(true);
              }}
              leftIcon={<Lock className="w-3.5 h-3.5" />}
            >
              Change Password
            </Button>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <Alert variant="danger" title="Profile Notice" onClose={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}
        {successMsg && (
          <Alert variant="success" title="Success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        )}

        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center gap-2 text-zinc-400">
            <Spinner size="lg" />
            <p className="text-xs">Loading profile details...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Contact & Account Overview */}
            <div className="space-y-6">
              {/* Contact Information Card */}
              <Card>
                <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <UserIcon className="w-4 h-4 text-indigo-500" />
                    Contact & Identity
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-3.5 text-xs">
                  <div>
                    <span className="text-zinc-400 block font-medium">Username</span>
                    <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                      @{activeUser?.username}
                    </span>
                  </div>

                  <div>
                    <span className="text-zinc-400 block font-medium flex items-center gap-1">
                      <Mail className="w-3 h-3 text-zinc-400" /> Email Address
                    </span>
                    <span className="text-zinc-900 dark:text-zinc-100">
                      {activeUser?.email || 'Not configured'}
                    </span>
                  </div>

                  <div>
                    <span className="text-zinc-400 block font-medium flex items-center gap-1">
                      <Phone className="w-3 h-3 text-zinc-400" /> Contact Phone
                    </span>
                    <span className="text-zinc-900 dark:text-zinc-100 font-mono">
                      {profile?.phone_number || 'Not provided'}
                    </span>
                  </div>

                  <div>
                    <span className="text-zinc-400 block font-medium">Account Status</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">
                      {activeUser?.account_status || 'ACTIVE'}
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Assigned Divisions / Verticals */}
              <Card>
                <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-500" />
                    Assigned Divisions
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-2 text-xs">
                  {activeUser?.verticals && activeUser.verticals.length > 0 ? (
                    activeUser.verticals.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700"
                      >
                        <span className="font-semibold text-zinc-900 dark:text-zinc-100">{v.name}</span>
                        {v.is_primary && (
                          <span className="text-[10px] bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded font-bold">
                            Primary
                          </span>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-zinc-400 italic">No assigned vertical divisions.</p>
                  )}
                </CardContent>
              </Card>

              {/* Account Timestamps */}
              <Card>
                <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Clock className="w-4 h-4 text-purple-500" />
                    Activity History
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-3 text-xs">
                  <div>
                    <span className="text-zinc-400 block font-medium">Last Login</span>
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {activeUser?.last_login_at
                        ? formatAuditDateTime(activeUser.last_login_at)
                        : 'First Session (Current)'}
                    </span>
                  </div>
                  {activeUser?.current_login_at && (
                    <div>
                      <span className="text-zinc-400 block font-medium">Current Session Started</span>
                      <span className="text-zinc-700 dark:text-zinc-300">
                        {formatAuditDateTime(activeUser.current_login_at)}
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="text-zinc-400 block font-medium">Member Since</span>
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {formatAuditDateTime(activeUser?.created_at || profile?.account_created_at || profile?.created_at)}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column: Professional Experience & Duties */}
            <div className="lg:col-span-2 space-y-6">
              {/* Professional Capabilities & Specialization Card */}
              <Card>
                <CardHeader className="pb-3 border-b border-zinc-100 dark:border-zinc-800">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Briefcase className="w-4 h-4 text-indigo-500" />
                    Professional Profile & Specialization
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-5 space-y-5 text-xs">
                  {/* Primary Specialization */}
                  <div>
                    <h4 className="font-bold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider text-[11px] mb-1.5 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                      Primary Specialization
                    </h4>
                    <p className="text-zinc-900 dark:text-zinc-100 font-medium bg-zinc-50 dark:bg-zinc-800/40 p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800">
                      {profile?.specialization || 'General Sports Department Operations'}
                    </p>
                  </div>

                  {/* Operational Capabilities & Duties */}
                  <div>
                    <h4 className="font-bold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider text-[11px] mb-1.5 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-indigo-500" />
                      Operational Duties & Capabilities
                    </h4>
                    <p className="text-zinc-700 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-800/40 p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 leading-relaxed whitespace-pre-line">
                      {profile?.operational_capability ||
                        'Equipment management, ground logistics, event check-in, scorekeeping support.'}
                    </p>
                  </div>

                  {/* Certifications */}
                  <div>
                    <h4 className="font-bold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider text-[11px] mb-2 flex items-center gap-1.5">
                      <Award className="w-3.5 h-3.5 text-amber-500" />
                      Certifications & Qualifications
                    </h4>
                    {profile?.certifications && profile.certifications.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {profile.certifications.map((cert, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60 font-semibold"
                          >
                            <CheckCircle2 className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                            {cert}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-zinc-400 italic">No certifications listed.</p>
                    )}
                  </div>

                  {/* Operational Notes */}
                  {profile?.profile_notes && (
                    <div>
                      <h4 className="font-bold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider text-[11px] mb-1.5">
                        Profile Notes
                      </h4>
                      <p className="text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/40 p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 italic">
                        {profile.profile_notes}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 1. EDIT PROFILE MODAL                                             */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          title="Edit Profile"
          description="Update your contact details, operational specialization, and availability."
        >
          <form onSubmit={handleSaveProfile} className="space-y-4 text-xs">
            {editError && (
              <Alert variant="danger" title="Update Failed">
                {editError}
              </Alert>
            )}

            {/* Group 1: Contact Information */}
            <div className="space-y-3 p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
              <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-indigo-500" />
                Contact Information
              </h4>
              <Input
                label="Contact Phone Number"
                placeholder="e.g. +1 555-0199"
                value={editForm.phone_number}
                onChange={(e) => setEditForm({ ...editForm, phone_number: e.target.value })}
              />
            </div>

            {/* Group 2: Professional Information */}
            <div className="space-y-3 p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
              <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5 text-indigo-500" />
                Professional Information
              </h4>
              <Input
                label="Primary Specialization"
                placeholder="e.g. Tournament Operations, Equipment Logistics"
                value={editForm.specialization}
                onChange={(e) => setEditForm({ ...editForm, specialization: e.target.value })}
              />
              <div className="space-y-1">
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                  Operational Duties & Capabilities
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe your standard duties and capabilities..."
                  value={editForm.operational_capability}
                  onChange={(e) => setEditForm({ ...editForm, operational_capability: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <Input
                label="Certifications (comma-separated)"
                placeholder="e.g. First Aid CPR, FA Referee Level 2"
                value={editForm.certifications_text}
                onChange={(e) => setEditForm({ ...editForm, certifications_text: e.target.value })}
              />
            </div>

            {/* Group 3: Availability & Notes */}
            <div className="space-y-3 p-3.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700">
              <h4 className="font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-indigo-500" />
                Availability & Notes
              </h4>
              <div className="space-y-1">
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                  Current Availability
                </label>
                <select
                  value={editForm.availability}
                  onChange={(e) => setEditForm({ ...editForm, availability: e.target.value as UserAvailability })}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="AVAILABLE">Available</option>
                  <option value="BUSY">Busy / On Duty</option>
                  <option value="ON_LEAVE">On Leave</option>
                  <option value="EMERGENCY_ONLY">Emergency Only</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300">
                  Profile Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="Optional scheduling or operational notes..."
                  value={editForm.profile_notes}
                  onChange={(e) => setEditForm({ ...editForm, profile_notes: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsEditOpen(false)}
                disabled={editLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={editLoading}
              >
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>

        {/* ------------------------------------------------------------------ */}
        {/* 2. CHANGE PASSWORD MODAL                                          */}
        {/* ------------------------------------------------------------------ */}
        <Modal
          isOpen={isPasswordOpen}
          onClose={() => setIsPasswordOpen(false)}
          title="Change Password"
          description="Enter your current password and choose a secure new password."
        >
          <form onSubmit={handleChangePassword} className="space-y-4 text-xs">
            {passwordError && (
              <Alert variant="danger" title="Password Change Failed">
                {passwordError}
              </Alert>
            )}

            <Input
              label="Current Password"
              type="password"
              required
              placeholder="Enter current password..."
              value={passwordForm.current_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
            />

            <Input
              label="New Password"
              type="password"
              required
              placeholder="At least 8 characters..."
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
            />

            {/* PASSWORD COMBINATION GUIDE & CHECKLIST */}
            <PasswordRequirements
              password={passwordForm.new_password}
              confirmPassword={passwordForm.confirm_password}
            />

            <Input
              label="Confirm New Password"
              type="password"
              required
              placeholder="Re-enter new password..."
              value={passwordForm.confirm_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
            />

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsPasswordOpen(false)}
                disabled={passwordLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={passwordLoading}
                leftIcon={<Lock className="w-3.5 h-3.5" />}
              >
                Update Password
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </AppShell>
  );
}
