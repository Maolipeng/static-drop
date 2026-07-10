"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { uploadZip, uploadFolder, formatBytes, type ApiError } from "@/lib/api";
import { useI18n } from "@/components/LanguageProvider";

type Status = "idle" | "uploading" | "success" | "error";
type Mode = "zip" | "folder";

export function DropZone() {
  const { messages } = useI18n();
  const router = useRouter();
  const zipInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [uploadLabel, setUploadLabel] = useState("");
  const [siteName, setSiteName] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [error, setError] = useState<string>("");
  const [errorCode, setErrorCode] = useState<string>("");

  // Build env object from optional fields
  const buildEnv = useCallback((): Record<string, string> | undefined => {
    const env: Record<string, string> = {};
    if (apiUrl.trim()) {
      env["API_URL"] = apiUrl.trim();
    }
    return Object.keys(env).length > 0 ? env : undefined;
  }, [apiUrl]);

  const handleZipFile = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".zip")) {
        setError(messages.upload.invalidZip);
        setErrorCode("VALIDATION_ERROR");
        setStatus("error");
        return;
      }

      setUploadLabel(file.name);
      setError("");
      setErrorCode("");
      setStatus("uploading");
      setProgress(0);

      uploadZip(file, siteName || undefined, (pct) => setProgress(pct), buildEnv())
        .then((result) => {
          setStatus("success");
          setProgress(100);
          router.push(`/deployments/${result.id}`);
        })
        .catch((err: ApiError) => {
          setStatus("error");
          setError(err.error || messages.upload.failed);
          setErrorCode(err.code || "INTERNAL");
        });
    },
    [siteName, router, buildEnv],
  );

  const handleFolderFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      if (fileArray.length === 0) {
        setError(messages.upload.noFiles);
        setErrorCode("VALIDATION_ERROR");
        setStatus("error");
        return;
      }

      // Derive a display label from the first file's webkitRelativePath
      const firstPath = (fileArray[0] as File & { webkitRelativePath?: string }).webkitRelativePath;
      const folderName = firstPath ? firstPath.split("/")[0] : "folder";
      setUploadLabel(`${folderName}/ (${fileArray.length} files)`);
      setError("");
      setErrorCode("");
      setStatus("uploading");
      setProgress(0);

      uploadFolder(fileArray, siteName || undefined, (pct) => setProgress(pct), buildEnv())
        .then((result) => {
          setStatus("success");
          setProgress(100);
          router.push(`/deployments/${result.id}`);
        })
        .catch((err: ApiError) => {
          setStatus("error");
          setError(err.error || messages.upload.failed);
          setErrorCode(err.code || "INTERNAL");
        });
    },
    [siteName, router, buildEnv],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const items = e.dataTransfer.items;
      // Check if a directory was dropped (use DataTransferItem API)
      if (items && items.length > 0 && typeof items[0].webkitGetAsEntry === "function") {
        const entry = items[0].webkitGetAsEntry();
        if (entry && entry.isDirectory) {
          // Traverse the directory recursively
          traverseDirectory(entry).then(handleFolderFiles).catch(() => {
            setError(messages.upload.droppedFolderError);
            setErrorCode("VALIDATION_ERROR");
            setStatus("error");
          });
          return;
        }
      }

      // Fall back to file drop (zip)
      const file = e.dataTransfer.files[0];
      if (file) handleZipFile(file);
    },
    [handleZipFile, handleFolderFiles],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError("");
    setProgress(0);
    setUploadLabel("");
    setErrorCode("");
  }, []);

  return (
    <div className="w-full">
      {/* Optional name field */}
      <div className="mb-4">
        <label
          htmlFor="siteName"
          className="mb-1 block text-sm font-medium text-slate-700"
        >
          {messages.upload.siteName} <span className="text-slate-400">({messages.upload.optional})</span>
        </label>
        <input
          id="siteName"
          type="text"
          value={siteName}
          onChange={(e) => setSiteName(e.target.value)}
          placeholder={messages.upload.siteNamePlaceholder}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          disabled={status === "uploading"}
        />
      </div>

      {/* Optional backend API URL */}
      <div className="mb-4">
        <label
          htmlFor="apiUrl"
          className="mb-1 block text-sm font-medium text-slate-700"
        >
          {messages.upload.apiUrl} <span className="text-slate-400">({messages.upload.optional})</span>
        </label>
        <input
          id="apiUrl"
          type="url"
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          placeholder={messages.upload.apiUrlPlaceholder}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          disabled={status === "uploading"}
        />
        <p className="mt-1 text-xs text-slate-400">
          {messages.upload.apiUrlHelp}{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5">window.__STATICDROP_ENV__.API_URL</code>.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={`
          relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition
          ${isDragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-400 hover:bg-slate-50"}
          ${status === "uploading" ? "cursor-wait border-brand-300" : ""}
          ${status === "error" ? "border-red-400 bg-red-50" : ""}
        `}
      >
        <input
          ref={zipInputRef}
          type="file"
          accept=".zip"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleZipFile(file);
          }}
          className="hidden"
          disabled={status === "uploading"}
        />
        <input
          ref={folderInputRef}
          type="file"
          // @ts-expect-error webkitdirectory is a non-standard but widely supported attribute
          webkitdirectory=""
          directory=""
          multiple
          onChange={(e) => {
            if (e.target.files) handleFolderFiles(e.target.files);
          }}
          className="hidden"
          disabled={status === "uploading"}
        />

        {status === "idle" && (
          <>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="mb-4 h-12 w-12 text-slate-400"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-lg font-medium text-slate-700">
              {messages.upload.dropTitle}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {messages.upload.dropDescription}{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-brand-600">.zip</code>{" "}
              {messages.upload.orA}{" "}<strong className="text-slate-500">{messages.upload.folder}</strong> — {messages.upload.supported}
            </p>
            <div className="mt-4 flex gap-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  zipInputRef.current?.click();
                }}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
                {messages.upload.chooseZip}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  folderInputRef.current?.click();
                }}
                className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
                </svg>
                {messages.upload.chooseFolder}
              </button>
            </div>
          </>
        )}

        {status === "uploading" && (
          <div className="w-full max-w-md">
            <div className="mb-3 flex items-center justify-center gap-2 text-slate-600">
              <svg
                className="h-5 w-5 animate-spin text-brand-600"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <span className="font-medium">{messages.upload.uploading} {uploadLabel}…</span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-brand-600 transition-all duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-2 text-center text-sm text-slate-500">
              {progress}% — {messages.upload.progress}
            </p>
          </div>
        )}

        {status === "error" && (
          <div className="text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="mx-auto mb-3 h-12 w-12 text-red-500"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
              />
            </svg>
            <p className="text-lg font-medium text-red-700">{messages.upload.failed}</p>
            <p className="mt-1 max-w-sm text-sm text-red-600">{error}</p>
            {errorCode && (
              <p className="mt-1 text-xs text-red-400">{messages.upload.code}: {errorCode}</p>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                reset();
              }}
              className="mt-4 rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50"
            >
              {messages.upload.tryAgain}
            </button>
          </div>
        )}
      </div>

      {/* Validation hints */}
      <div className="mt-6 grid grid-cols-2 gap-3 text-xs text-slate-500 sm:grid-cols-4">
        <div className="rounded-lg bg-slate-100 p-3">
            <p className="font-semibold text-slate-600">{messages.upload.maxUpload}</p>
          <p>100 MB</p>
        </div>
        <div className="rounded-lg bg-slate-100 p-3">
            <p className="font-semibold text-slate-600">{messages.upload.maxTotal}</p>
          <p>500 MB</p>
        </div>
        <div className="rounded-lg bg-slate-100 p-3">
            <p className="font-semibold text-slate-600">{messages.upload.maxFiles}</p>
          <p>5,000</p>
        </div>
        <div className="rounded-lg bg-slate-100 p-3">
            <p className="font-semibold text-slate-600">{messages.upload.mustHave}</p>
          <p>index.html</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Recursively traverse a FileSystemDirectoryEntry and collect all files
 * with their relative paths (mimicking webkitRelativePath).
 */
async function traverseDirectory(
  entry: FileSystemEntry,
  path: string = "",
): Promise<File[]> {
  return new Promise((resolve, reject) => {
    if (entry.isFile) {
      (entry as FileSystemFileEntry).file(
        (file: File) => {
          // Create a new File with the correct name including path
          const fullPath = path ? `${path}/${file.name}` : file.name;
          // We can't set webkitRelativePath, so we use a custom property
          // The uploadFolder function checks webkitRelativePath first, then file.name
          // We'll encode the path in the filename when appending to FormData
          const fileWithPath = Object.defineProperty(file, "webkitRelativePath", {
            value: fullPath,
            writable: false,
          }) as File;
          resolve([fileWithPath]);
        },
        (err) => reject(err),
      );
    } else if (entry.isDirectory) {
      const dirReader = (entry as FileSystemDirectoryEntry).createReader();
      const allFiles: File[] = [];
      const currentPath = path ? `${path}/${entry.name}` : entry.name;

      const readEntries = () => {
        dirReader.readEntries(
          async (entries: FileSystemEntry[]) => {
            if (entries.length === 0) {
              resolve(allFiles);
              return;
            }
            for (const e of entries) {
              try {
                const files = await traverseDirectory(e, currentPath);
                allFiles.push(...files);
              } catch (err) {
                reject(err);
                return;
              }
            }
            readEntries();
          },
          (err) => reject(err),
        );
      };
      readEntries();
    } else {
      resolve([]);
    }
  });
}
