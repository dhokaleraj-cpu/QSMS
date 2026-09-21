import SwiftUI
import WebKit

struct QCMSWebView: UIViewRepresentable {
    let urlString: String
    @Binding var menuExpanded: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic
        webView.customUserAgent = "QCMSMobileIOS/0.1.0"
        context.coordinator.webView = webView
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.reload), name: .qcmsReload, object: nil)
        if let url = URL(string: urlString) { webView.load(URLRequest(url: url)) }
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.parent = self
        context.coordinator.applyNavigation(open: menuExpanded)
    }

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        NotificationCenter.default.removeObserver(coordinator)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: QCMSWebView
        weak var webView: WKWebView?
        init(_ parent: QCMSWebView) { self.parent = parent }

        @objc func reload() { webView?.reload() }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            DispatchQueue.main.async { self.parent.menuExpanded = false }
            installController()
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
            if ["http", "https"].contains(url.scheme?.lowercased() ?? "") { decisionHandler(.allow) }
            else { UIApplication.shared.open(url); decisionHandler(.cancel) }
        }

        func installController() {
            let script = """
            (function(){
              window.__qcmsMobileNavOpen=false;
              function apply(){
                var open=!!window.__qcmsMobileNavOpen;
                var workspace=document.querySelector('.st-key-qcms_workspace,[class~="st-key-qcms_workspace"]');
                var row=workspace?workspace.querySelector('[data-testid="stHorizontalBlock"]'):null;
                if(row){row.style.flexDirection=open?'column':'row';row.style.alignItems='stretch';}
                var rail=document.querySelector('.st-key-fsi_left_rail,[class~="st-key-fsi_left_rail"]');
                var railCol=rail?rail.closest('[data-testid="column"]'):null;
                if(railCol){railCol.style.display=open?'block':'none';railCol.style.width=open?'100%':'0';railCol.style.flex=open?'1 1 100%':'0 0 0';}
                var content=document.querySelector('.st-key-qcms_content,[class~="st-key-qcms_content"]');
                var contentCol=content?content.closest('[data-testid="column"]'):null;
                if(contentCol){contentCol.style.display='block';contentCol.style.width='100%';contentCol.style.flex='1 1 100%';}
                document.querySelectorAll('[class*="st-key-fsi_module_subnav_"]').forEach(function(el){el.style.display=open?'block':'none';});
              }
              window.__qcmsApplyMobileNav=apply;
              if(window.__qcmsMobileNavObserver){try{window.__qcmsMobileNavObserver.disconnect();}catch(e){}}
              window.__qcmsMobileNavObserver=new MutationObserver(function(){requestAnimationFrame(apply);});
              window.__qcmsMobileNavObserver.observe(document.documentElement,{childList:true,subtree:true});
              apply();
            })();
            """
            webView?.evaluateJavaScript(script)
        }

        func applyNavigation(open: Bool) {
            let js = "window.__qcmsMobileNavOpen=\(open ? "true" : "false");if(window.__qcmsApplyMobileNav){window.__qcmsApplyMobileNav();}"
            webView?.evaluateJavaScript(js)
        }
    }
}
