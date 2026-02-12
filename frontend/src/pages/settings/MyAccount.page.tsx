import { useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { useAuthContext } from "../../hooks/useAuthContext";
import InputBox from "../../components/ui/InputBox";
import { Button } from "../../components/ui/Button";
import { updatePasswordHandler } from "../../handlers/authHandlers";
import { toast } from "react-hot-toast";

const MyAccountPage = () => {
  const { user } = useAuthContext();
  const [showPasswordUpdate, setShowPasswordUpdate] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

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
    } catch (err) {
      console.error("Failed to update password", err);
      toast.error("Failed to update password");
    } finally {
      setPasswordBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="My Account"
        description="View your profile details and personal preferences."
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
        <div className="border border-gray-200 rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Account Security</h3>
              <p className="text-xs text-gray-600">Update your password to secure your account.</p>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
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
                <Button variant="primary" onClick={handleUpdatePassword} disabled={passwordBusy}>
                  {passwordBusy ? "Updating…" : "Update"}
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default MyAccountPage;
