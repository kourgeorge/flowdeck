import type { FormEvent } from 'react';
import type { MeProfile } from '../../services/authApi';
import {
  PROFILE_DANGER_BUTTON_CLASS,
  PROFILE_INPUT_CLASS,
  PROFILE_MUTED_PANEL_CLASS,
  PROFILE_PANEL_CLASS,
  PROFILE_PILL_CLASS,
  PROFILE_PRIMARY_BUTTON_CLASS,
} from './profileStyles';

type ProfileAccountTabProps = {
  profile: MeProfile | null;
  name: string;
  nameSaving: boolean;
  nameMessage: string | null;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
  passwordSaving: boolean;
  passwordMessage: string | null;
  deletePassword: string;
  deleteConfirmText: string;
  deleteLoading: boolean;
  deleteError: string | null;
  deleteConfirmLabel: string;
  onNameChange: (value: string) => void;
  onCurrentPasswordChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onDeletePasswordChange: (value: string) => void;
  onDeleteConfirmTextChange: (value: string) => void;
  onSaveName: (event: FormEvent) => void;
  onChangePassword: (event: FormEvent) => void;
  onDeleteAccount: (event: FormEvent) => void;
};

export default function ProfileAccountTab({
  profile,
  name,
  nameSaving,
  nameMessage,
  currentPassword,
  newPassword,
  confirmPassword,
  passwordSaving,
  passwordMessage,
  deletePassword,
  deleteConfirmText,
  deleteLoading,
  deleteError,
  deleteConfirmLabel,
  onNameChange,
  onCurrentPasswordChange,
  onNewPasswordChange,
  onConfirmPasswordChange,
  onDeletePasswordChange,
  onDeleteConfirmTextChange,
  onSaveName,
  onChangePassword,
  onDeleteAccount,
}: ProfileAccountTabProps) {
  return (
    <div className="space-y-6">
      {profile && (
        <section className={`${PROFILE_PANEL_CLASS} p-6`}>
          <span className={`${PROFILE_PILL_CLASS} border-slate-500/30 bg-slate-500/10 text-slate-200`}>
            Identity
          </span>
          <h2 className="mt-4 text-xl font-semibold text-white">Email</h2>
          <div className={`${PROFILE_MUTED_PANEL_CLASS} mt-5 px-4 py-4`}>
            <p className="text-base font-medium text-white">{profile.email}</p>
            <p className="mt-1 text-xs text-slate-500">Email cannot be changed here.</p>
          </div>
        </section>
      )}

      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        <span className={`${PROFILE_PILL_CLASS} border-cyan-400/30 bg-cyan-400/10 text-cyan-100`}>
          Profile
        </span>
        <h2 className="mt-4 text-xl font-semibold text-white">Display name</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          Update the name shown across your FlowDeck account.
        </p>

        <form onSubmit={onSaveName} className="mt-6 space-y-4">
          <div>
            <label htmlFor="profile-name" className="mb-2 block text-sm font-medium text-slate-200">
              Name
            </label>
            <input
              id="profile-name"
              type="text"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
              className={PROFILE_INPUT_CLASS}
              placeholder="Your name"
            />
          </div>
          {nameMessage ? (
            <p className={`text-sm ${nameMessage.startsWith('Name updated') ? 'text-emerald-300' : 'text-red-300'}`}>
              {nameMessage}
            </p>
          ) : null}
          <button type="submit" disabled={nameSaving} className={PROFILE_PRIMARY_BUTTON_CLASS}>
            {nameSaving ? 'Saving...' : 'Save name'}
          </button>
        </form>
      </section>

      {profile?.has_password ? (
        <section className={`${PROFILE_PANEL_CLASS} p-6`}>
          <span className={`${PROFILE_PILL_CLASS} border-blue-400/30 bg-blue-400/10 text-blue-100`}>
            Security
          </span>
          <h2 className="mt-4 text-xl font-semibold text-white">Change password</h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Set a new password for direct sign-in to your account.
          </p>

          <form onSubmit={onChangePassword} className="mt-6 space-y-4">
            <div>
              <label htmlFor="profile-current-password" className="mb-2 block text-sm font-medium text-slate-200">
                Current password
              </label>
              <input
                id="profile-current-password"
                type="password"
                value={currentPassword}
                onChange={(event) => onCurrentPasswordChange(event.target.value)}
                className={PROFILE_INPUT_CLASS}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <div>
              <label htmlFor="profile-new-password" className="mb-2 block text-sm font-medium text-slate-200">
                New password
              </label>
              <input
                id="profile-new-password"
                type="password"
                value={newPassword}
                onChange={(event) => onNewPasswordChange(event.target.value)}
                className={PROFILE_INPUT_CLASS}
                placeholder="••••••••"
                autoComplete="new-password"
                minLength={6}
              />
            </div>
            <div>
              <label htmlFor="profile-confirm-password" className="mb-2 block text-sm font-medium text-slate-200">
                Confirm new password
              </label>
              <input
                id="profile-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(event) => onConfirmPasswordChange(event.target.value)}
                className={PROFILE_INPUT_CLASS}
                placeholder="••••••••"
                autoComplete="new-password"
                minLength={6}
              />
            </div>
            {passwordMessage ? (
              <p className={`text-sm ${passwordMessage.startsWith('Password updated') ? 'text-emerald-300' : 'text-red-300'}`}>
                {passwordMessage}
              </p>
            ) : null}
            <button type="submit" disabled={passwordSaving} className={PROFILE_PRIMARY_BUTTON_CLASS}>
              {passwordSaving ? 'Updating...' : 'Change password'}
            </button>
          </form>
        </section>
      ) : null}

      <section className={`${PROFILE_PANEL_CLASS} border-red-900/50 p-6`}>
        <span className={`${PROFILE_PILL_CLASS} border-red-400/30 bg-red-400/10 text-red-200`}>
          Dangerous action
        </span>
        <h2 className="mt-4 text-xl font-semibold text-red-200">Delete account</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          This permanently deletes your account and all associated data. This
          action cannot be undone.
        </p>

        <form onSubmit={onDeleteAccount} className="mt-6 space-y-4">
          {profile?.has_password ? (
            <div>
              <label htmlFor="delete-password" className="mb-2 block text-sm font-medium text-slate-200">
                Your password
              </label>
              <input
                id="delete-password"
                type="password"
                value={deletePassword}
                onChange={(event) => onDeletePasswordChange(event.target.value)}
                className={PROFILE_INPUT_CLASS}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
          ) : null}
          <div>
            <label htmlFor="delete-confirm-text" className="mb-2 block text-sm font-medium text-slate-200">
              Type {deleteConfirmLabel} to confirm
            </label>
            <input
              id="delete-confirm-text"
              type="text"
              value={deleteConfirmText}
              onChange={(event) => onDeleteConfirmTextChange(event.target.value)}
              className={PROFILE_INPUT_CLASS}
              placeholder={deleteConfirmLabel}
              autoComplete="off"
            />
          </div>
          {deleteError ? <p className="text-sm text-red-300">{deleteError}</p> : null}
          <button
            type="submit"
            disabled={
              deleteLoading ||
              deleteConfirmText !== deleteConfirmLabel ||
              Boolean(profile?.has_password && !deletePassword.trim())
            }
            className={PROFILE_DANGER_BUTTON_CLASS}
          >
            {deleteLoading ? 'Deleting...' : 'Delete my account'}
          </button>
        </form>
      </section>
    </div>
  );
}
