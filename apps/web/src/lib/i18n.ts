export type Locale = "en" | "zh";

const messages = {
  en: {
    nav: { upload: "Upload", history: "History", settings: "Settings", switchTo: "中文" },
    home: {
      title: "Deploy your static site in seconds",
      description: "Drag and drop your build output",
      descriptionEnd: "— we’ll handle validation, extraction, and hosting.",
    },
    upload: {
      siteName: "Project name", selectProject: "Project", newProject: "New project", optional: "optional", siteNamePlaceholder: "e.g. My Portfolio",
      apiUrl: "Backend API URL", apiUrlPlaceholder: "e.g. https://api.example.com",
      apiUrlHelp: "If your frontend needs a backend API, enter its URL here. It will be available in your app as",
      github: "GitHub repository", githubPlaceholder: "https://github.com/owner/repository", githubRef: "Branch or tag", githubDeploy: "Deploy from GitHub", githubMode: "GitHub", uploadMode: "Upload files", githubHelp: "The repository must contain an index.html in its root or build folder.",
      dropTitle: "Drop your build output here", dropDescription: "Drag a", orA: "or a", folder: "folder",
      supported: "Vite dist, React build, Next.js out, etc.", chooseZip: "Choose .zip", chooseFolder: "Choose folder",
      uploading: "Uploading", progress: "validating, extracting, deploying…", failed: "Deployment failed",
      code: "Code", tryAgain: "Try again", maxUpload: "Max upload", maxTotal: "Max total", maxFiles: "Max files", mustHave: "Must have",
      noFiles: "No files found in the selected folder", invalidZip: "Please upload a .zip file",
      droppedFolderError: "Failed to read dropped folder", networkError: "Network error during upload",
      aborted: "Upload aborted", invalidResponse: "Invalid response from server",
    },
    deployments: {
      title: "Deployment History", total: (count: number) => `${count} ${count === 1 ? "deployment" : "deployments"} total`, version: "Version",
      newDeployment: "New deployment", noDeployments: "No deployments yet", noDeploymentsHelp: "Upload your first static site to get started.",
      uploadNow: "Upload now", nameId: "Name / ID", files: "Files", size: "Size", deployed: "Deployed", view: "View →", loadError: "Failed to load deployments",
    },
    detail: {
      success: "Deployed successfully!", successHelp: "Your site is live and ready to share.", liveUrl: "Live URL", openSite: "Open site",
      project: "Project", version: "Version", deployId: "Deploy ID", fileCount: "File count", totalSize: "Total size", source: "Source", name: "Name", deployedAt: "Deployed at",
      newDeployment: "New deployment", viewAll: "View all", domains: "Domains", addDomain: "Add", autoConfigureDomain: "Auto-configure with Cloudflare", dnsProvisioned: "DNS records created. Verify after propagation.", verifyDomain: "Verify", removeDomain: "Remove", verified: "verified", pending: "pending", domainPlaceholder: "www.example.com", domainFailed: "Operation failed",
    },
    settings: {
      title: "Settings", systemHealth: "System Health", error: "Error", database: "Database", dataDirectory: "Data directory", deploymentsPath: "Deployments path",
      authentication: "Authentication", tokenConfigured: "Token configured", defaultToken: "Default token — please set DEPLOY_TOKEN",
      tokenHelp: "Token is configured server-side via the DEPLOY_TOKEN environment variable.", uploadLimits: "Upload Limits", maxZip: "Max zip size",
      maxUncompressed: "Max total (uncompressed)", maxFile: "Max single file", maxCount: "Max file count", limitsHelp: "These limits can be overridden via environment variables on the API server.",
    },
    common: { copy: "Copy", copied: "Copied!", failedToReachApi: "Failed to reach API" },
    auth: { title: "Sign in", email: "Email", password: "Password", submit: "Sign in", register: "Create account", switchRegister: "Need an account? Create one", switchLogin: "Already have an account? Sign in", disabled: "User authentication is disabled. Set AUTH_MODE=users to enable it.", failed: "Authentication failed" },
  },
  zh: {
    nav: { upload: "上传", history: "部署记录", settings: "设置", switchTo: "English" },
    home: { title: "几秒钟部署你的静态网站", description: "拖拽或选择构建产物", descriptionEnd: "— 我们会完成校验、解压和托管。" },
    upload: {
      siteName: "项目名称", selectProject: "项目", newProject: "新建项目", optional: "可选", siteNamePlaceholder: "例如：我的作品集", apiUrl: "后端 API 地址", apiUrlPlaceholder: "例如：https://api.example.com",
      apiUrlHelp: "如果前端需要后端 API，请在这里填写地址。它将在应用中通过以下变量访问：", github: "GitHub 仓库", githubPlaceholder: "https://github.com/用户/仓库", githubRef: "分支或标签", githubDeploy: "从 GitHub 部署", githubMode: "GitHub", uploadMode: "上传文件", githubHelp: "仓库根目录或构建目录中需要包含 index.html。", dropTitle: "将构建产物拖到这里", dropDescription: "拖入", orA: "或选择一个", folder: "文件夹",
      supported: "支持 Vite dist、React build、Next.js out 等构建产物。", chooseZip: "选择 .zip", chooseFolder: "选择文件夹", uploading: "正在上传", progress: "正在校验、解压并部署…", failed: "部署失败",
      code: "错误码", tryAgain: "重试", maxUpload: "最大上传", maxTotal: "最大总大小", maxFiles: "最大文件数", mustHave: "必须包含", noFiles: "所选文件夹中没有找到文件", invalidZip: "请上传 .zip 文件",
      droppedFolderError: "读取拖入的文件夹失败", networkError: "上传过程中网络错误", aborted: "上传已取消", invalidResponse: "服务器返回了无效响应",
    },
    deployments: {
      title: "部署记录", total: (count: number) => `共 ${count} 次部署`, version: "版本", newDeployment: "新建部署", noDeployments: "还没有部署记录", noDeploymentsHelp: "上传你的第一个静态网站即可开始。",
      uploadNow: "立即上传", nameId: "名称 / ID", files: "文件数", size: "大小", deployed: "部署时间", view: "查看 →", loadError: "加载部署记录失败",
    },
    detail: {
      success: "部署成功！", successHelp: "你的网站已经上线，可以分享了。", liveUrl: "访问地址", openSite: "打开网站", project: "项目", version: "版本", deployId: "部署 ID", fileCount: "文件数", totalSize: "总大小", source: "来源", name: "名称", deployedAt: "部署时间", newDeployment: "新建部署", viewAll: "查看全部", domains: "域名", addDomain: "添加", autoConfigureDomain: "使用 Cloudflare 自动配置", dnsProvisioned: "DNS 记录已创建，等待传播后请点击验证。", verifyDomain: "验证", removeDomain: "移除", verified: "已验证", pending: "待验证", domainPlaceholder: "www.example.com", domainFailed: "操作失败",
    },
    settings: {
      title: "设置", systemHealth: "系统健康", error: "错误", database: "数据库", dataDirectory: "数据目录", deploymentsPath: "部署目录", authentication: "身份验证", tokenConfigured: "Token 已配置", defaultToken: "正在使用默认 Token — 请设置 DEPLOY_TOKEN", tokenHelp: "Token 通过 API 服务端的 DEPLOY_TOKEN 环境变量配置。", uploadLimits: "上传限制", maxZip: "最大 zip 大小", maxUncompressed: "最大总大小（解压后）", maxFile: "单文件最大大小", maxCount: "最大文件数", limitsHelp: "这些限制可以通过 API 服务端的环境变量覆盖。",
    },
    common: { copy: "复制", copied: "已复制！", failedToReachApi: "无法连接 API" },
    auth: { title: "登录", email: "邮箱", password: "密码", submit: "登录", register: "创建账号", switchRegister: "还没有账号？创建账号", switchLogin: "已有账号？登录", disabled: "用户认证未启用，请设置 AUTH_MODE=users。", failed: "认证失败" },
  },
} as const;

export type Messages = (typeof messages)[Locale];

export function getMessages(locale: Locale): Messages { return messages[locale]; }
