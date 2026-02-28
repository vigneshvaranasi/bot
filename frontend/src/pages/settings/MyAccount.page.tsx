import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { useAuthContext } from "../../hooks/useAuthContext";
import InputBox from "../../components/ui/InputBox";
import { Button } from "../../components/ui/Button";
import {
  updatePasswordHandler,
  getAvailableProviders,
  initiateLinkProvider,
  unlinkProvider,
} from "../../handlers/authHandlers";
import { toast } from "react-hot-toast";
import GoogleIcon from "../../assets/icons/google.svg";
import GithubIcon from "../../assets/icons/github.svg";
import MicrosoftIcon from "../../assets/icons/microsoft.svg";

const PROVIDER_META: Record<string, { label: string; icon: string }> = {
  google: { label: "Google", icon: GoogleIcon },
  github: { label: "GitHub", icon: GithubIcon },
  microsoft: { label: "Microsoft", icon: MicrosoftIcon },
};

const MyAccountPage = () => {
  const { user, refreshUser } = useAuthContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const [showPasswordUpdate, setShowPasswordUpdate] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const [showLocalSetup, setShowLocalSetup] = useState(false);
  const [localPassword, setLocalPassword] = useState("");
  const [localConfirm, setLocalConfirm] = useState("");
  const [localBusy, setLocalBusy] = useState(false);

  const [availableProviders, setAvailableProviders] = useState<string[]>([]);
  const [unlinkingProvider, setUnlinkingProvider] = useState<string | null>(null);

  const userIdentities = user?.auth_identities || [];
  const hasLocalAuth = userIdentities.includes("local");
  const identityCount = userIdentities.length;

  useEffect(() => {
    getAvailableProviders()
      .then(setAvailableProviders)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const linked = searchParams.get("linked");
    const linkError = searchParams.get("link_error");

    if (linked) {
      const label = PROVIDER_META[linked]?.label || linked;
      toast.success(`${label} account linked successfully!`);
      searchParams.delete("linked");
      setSearchParams(searchParams, { replace: true });
    }
    if (linkError) {
      toast.error(decodeURIComponent(linkError));
      searchParams.delete("link_error");
      setSearchParams(searchParams, { replace: true });
    }
  }, []);

  const handleUpdatePassword = async () => {
    if (!newPassword) {
      toast.error("Please enter a password");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      setPasswordBusy(true);
      await updatePasswordHandler(newPassword);
      toast.success("Password updated successfully");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordUpdate(false);
    } catch {
      toast.error("Failed to update password");
    } finally {
      setPasswordBusy(false);
    }
  };

  const handleSetupLocal = async () => {
    if (!localPassword) {
      toast.error("Please enter a password");
      return;
    }
    if (localPassword !== localConfirm) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      setLocalBusy(true);
      await updatePasswordHandler(localPassword);
      toast.success("Password authentication set up successfully");
      setLocalPassword("");
      setLocalConfirm("");
      setShowLocalSetup(false);
      await refreshUser();
    } catch {
      toast.error("Failed to set up password");
    } finally {
      setLocalBusy(false);
    }
  };

  const handleLinkOAuth = async (provider: string) => {
    try {
      const authUrl = await initiateLinkProvider(provider);
      window.location.href = authUrl;
    } catch {
      toast.error(`Failed to initiate ${PROVIDER_META[provider]?.label || provider} linking`);
    }
  };

  const handleUnlink = async (provider: string) => {
    try {
      setUnlinkingProvider(provider);
      await unlinkProvider(provider);
      const label = PROVIDER_META[provider]?.label || provider;
      toast.success(`${label} account unlinked`);
      await refreshUser();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to unlink provider";
      toast.error(detail);
    } finally {
      setUnlinkingProvider(null);
    }
  };

  const oauthProviders = availableProviders.filter((p) => p !== "local");

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="My Account"
        description="View your profile details and manage linked accounts."
      />

      <div className="flex flex-col gap-6">
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Profile</h3>
          <dl className="space-y-2 text-sm text-gray-700">
            <div className="flex justify-between">
              <dt className="text-gray-600">Email</dt>
              <dd className="font-medium">{user?.email || "-"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Role</dt>
              <dd className="font-medium">{user?.role || "-"}</dd>
            </div>
          </dl>
        </div>

        <div className="border border-gray-200 rounded-lg p-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Linked Accounts</h3>
            <p className="text-xs text-gray-600">
              Manage the authentication methods connected to your account.
            </p>
          </div>

          <div className="divide-y divide-gray-100">
            {availableProviders.includes("local") && (
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-5 h-5 text-gray-500"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span className="text-sm font-medium text-gray-900">Email & Password</span>
                </div>
                {hasLocalAuth ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">
                      Connected
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleUnlink("local")}
                      disabled={identityCount <= 1 || unlinkingProvider === "local"}
                    >
                      {unlinkingProvider === "local" ? "Removing..." : "Disconnect"}
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowLocalSetup(true)}
                  >
                    Set up password
                  </Button>
                )}
              </div>
            )}

            {showLocalSetup && !hasLocalAuth && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 my-2">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Password
                    </label>
                    <InputBox
                      variant="primary"
                      type="password"
                      value={localPassword}
                      onChange={setLocalPassword}
                      placeholder="Enter password"
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Confirm Password
                    </label>
                    <InputBox
                      variant="primary"
                      type="password"
                      value={localConfirm}
                      onChange={setLocalConfirm}
                      placeholder="Confirm password"
                      className="w-full"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="default"
                    onClick={() => {
                      setShowLocalSetup(false);
                      setLocalPassword("");
                      setLocalConfirm("");
                    }}
                  >
                    Cancel
                  </Button>
                  <Button variant="primary" onClick={handleSetupLocal} disabled={localBusy}>
                    {localBusy ? "Setting up..." : "Set up"}
                  </Button>
                </div>
              </div>
            )}

            {oauthProviders.map((provider) => {
              const meta = PROVIDER_META[provider];
              if (!meta) return null;
              const isLinked = userIdentities.includes(provider);
              return (
                <div
                  key={provider}
                  className="flex items-center justify-between py-3"
                >
                  <div className="flex items-center gap-3">
                    <img src={meta.icon} alt={meta.label} className="w-5 h-5" />
                    <span className="text-sm font-medium text-gray-900">{meta.label}</span>
                  </div>
                  {isLinked ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">
                        Connected
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleUnlink(provider)}
                        disabled={identityCount <= 1 || unlinkingProvider === provider}
                      >
                        {unlinkingProvider === provider ? "Removing..." : "Disconnect"}
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleLinkOAuth(provider)}
                    >
                      Connect
                    </Button>
                  )}
                </div>
              );
            })}
          </div>

          {identityCount <= 1 && (
            <p className="text-xs text-amber-600 mt-2">
              You must have at least one authentication method. Connect another provider before
              disconnecting your current one.
            </p>
          )}
        </div>

        {hasLocalAuth && (
          <div className="border border-gray-200 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Account Security</h3>
                <p className="text-xs text-gray-600">
                  Update your password to secure your account.
                </p>
              </div>
              {!showPasswordUpdate ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowPasswordUpdate(true)}
                >
                  Update password
                </Button>
              ) : null}
            </div>

            {showPasswordUpdate ? (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      New Password
                    </label>
                    <InputBox
                      variant="primary"
                      type="password"
                      value={newPassword}
                      onChange={setNewPassword}
                      placeholder="Enter new password"
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Confirm Password
                    </label>
                    <InputBox
                      variant="primary"
                      type="password"
                      value={confirmPassword}
                      onChange={setConfirmPassword}
                      placeholder="Confirm new password"
                      className="w-full"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="default"
                    onClick={() => {
                      setShowPasswordUpdate(false);
                      setNewPassword("");
                      setConfirmPassword("");
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleUpdatePassword}
                    disabled={passwordBusy}
                  >
                    {passwordBusy ? "Updating..." : "Update"}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default MyAccountPage;
