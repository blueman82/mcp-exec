/**
 * OktaAuthPrompt Component
 * Displays when waiting for Okta 2FA approval
 */

'use client';

interface OktaAuthPromptProps {
  server: string;
  isVisible: boolean;
}

export default function OktaAuthPrompt({
  server,
  isVisible,
}: OktaAuthPromptProps) {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 border border-blue-500 rounded-lg p-8 max-w-md">
        <div className="flex flex-col items-center space-y-4">
          {/* Loading spinner */}
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-500 border-t-transparent"></div>

          {/* Message */}
          <h2 className="text-xl font-bold text-white">
            Okta Authentication Required
          </h2>

          <p className="text-gray-300 text-center">
            Waiting for Okta push notification approval on <br />
            <span className="font-mono font-bold text-blue-400">{server}</span>
          </p>

          <div className="mt-4 p-4 bg-gray-900 rounded border border-gray-700 w-full">
            <ol className="text-sm text-gray-400 space-y-2 list-decimal list-inside">
              <li>Check your Okta Verify app</li>
              <li>Tap &ldquo;Approve&rdquo; to authenticate</li>
              <li>Connection will proceed automatically</li>
            </ol>
          </div>

          <p className="text-xs text-gray-500">
            This may take up to 60 seconds...
          </p>
        </div>
      </div>
    </div>
  );
}
