import SwiftUI
import WebKit

struct QCMSWebView: UIViewRepresentable {
    let urlString: String
    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic
        webView.customUserAgent = "QCMSMobileIOS/0.1.2"
        context.coordinator.webView = webView
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.reload), name: .qcmsReload, object: nil)
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.navigate(_:)), name: .qcmsNavigate, object: nil)
        if var parts = URLComponents(string: urlString) {
            parts.queryItems = [URLQueryItem(name: "native_mobile", value: "1")]
            if let url = parts.url { webView.load(URLRequest(url: url)) }
        }
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) { context.coordinator.parent = self }
    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) { NotificationCenter.default.removeObserver(coordinator) }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: QCMSWebView
        weak var webView: WKWebView?
        init(_ parent: QCMSWebView) { self.parent = parent }
        @objc func reload() { webView?.reload() }
        @objc func navigate(_ note: Notification) {
            guard let path = note.object as? String, var parts = URLComponents(string: parent.urlString) else { return }
            let base = parts.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            parts.path = "/" + ([base, path].filter { !$0.isEmpty }.joined(separator: "/"))
            parts.queryItems = [URLQueryItem(name: "native_mobile", value: "1")]
            parts.fragment = nil
            if let url = parts.url { webView?.load(URLRequest(url: url)) }
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { installMobileController() }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
            if ["http", "https"].contains(url.scheme?.lowercased() ?? "") { decisionHandler(.allow) }
            else { UIApplication.shared.open(url); decisionHandler(.cancel) }
        }
        func installMobileController() {
            let script = """
            (function(){
              function apply(){
                document.querySelectorAll('header[data-testid="stHeader"],div[data-testid="stToolbar"],div[data-testid="stDecoration"],section[data-testid="stSidebar"],.st-key-fsi_shell,[class~="st-key-fsi_shell"]').forEach(function(el){el.style.setProperty('display','none','important');});
                var shell=document.querySelector('.st-key-qcms_mobile_shell,[class~="st-key-qcms_mobile_shell"]'); if(shell){shell.style.display='none';}
                var workspace=document.querySelector('.st-key-qcms_workspace,[class~="st-key-qcms_workspace"]');
                var row=workspace?workspace.querySelector('[data-testid="stHorizontalBlock"]'):null;
                if(row){row.style.flexDirection='row';row.style.alignItems='stretch';}
                var rail=document.querySelector('.st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"]');
                var railCol=rail?rail.closest('[data-testid="column"]'):null;
                if(railCol){railCol.style.display='none';railCol.style.width='0';railCol.style.flex='0 0 0';}
                document.querySelectorAll('[class*="st-key-fsi_module_subnav_"]').forEach(function(el){el.style.display='none';});
                var content=document.querySelector('.st-key-qcms_content,[class~="st-key-qcms_content"]');
                var contentCol=content?content.closest('[data-testid="column"]'):null;
                if(contentCol){contentCol.style.display='block';contentCol.style.width='100%';contentCol.style.flex='1 1 100%';contentCol.style.maxWidth='100%';}
                var block=document.querySelector('[data-testid="stMainBlockContainer"]'); if(block){block.style.paddingLeft='0.65rem';block.style.paddingRight='0.65rem';block.style.paddingTop='0.5rem';}
              }
              if(window.__qcmsNativeObserver){try{window.__qcmsNativeObserver.disconnect();}catch(e){}}
              window.__qcmsNativeObserver=new MutationObserver(function(){requestAnimationFrame(apply);});
              window.__qcmsNativeObserver.observe(document.documentElement,{childList:true,subtree:true}); apply();
            })();
            """
            webView?.evaluateJavaScript(script)
        }
    }
}
