package ml.abic.ngoninana;

import android.net.http.SslCertificate;
import android.net.http.SslError;
import android.os.Bundle;
import android.util.Log;
import android.webkit.SslErrorHandler;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

import java.io.ByteArrayInputStream;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;

public class MainActivity extends BridgeActivity {

    // Empreinte SHA-256 du certificat auto-signe de developpement (voir
    // README : openssl ... -keyout .certs/key.pem -out .certs/cert.pem).
    // Ce certificat n'est PAS public (CN=ngoni-nana-test, jamais valide par
    // une autorite) : un navigateur ou une app qui ne connait pas cette
    // empreinte precise rejette la connexion. On ne fait PAS confiance a
    // n'importe quel certificat invalide (ce qui ouvrirait a une attaque
    // d'interception) - seulement a CELUI-CI, identifie par son empreinte.
    // Si le certificat est regenere (nouvelle empreinte), cette valeur doit
    // etre mise a jour et l'app reconstruite.
    private static final String EMPREINTE_SHA256_ATTENDUE =
            "7D:6E:8B:98:E8:28:BE:1B:E8:BC:D0:96:49:91:F8:FF:84:50:FF:5E:D2:6E:E5:81:07:A5:35:45:D2:9B:1C:BC";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        this.bridge.getWebView().setWebViewClient(new BridgeWebViewClient(this.bridge) {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                if (certificatCorrespondA(error.getCertificate(), EMPREINTE_SHA256_ATTENDUE)) {
                    handler.proceed();
                } else {
                    Log.w("NgoniNana", "Certificat SSL refuse (empreinte inattendue) : " + error);
                    handler.cancel();
                }
            }
        });
    }

    private static boolean certificatCorrespondA(SslCertificate certificat, String empreinteAttendue) {
        try {
            Bundle etat = SslCertificate.saveState(certificat);
            byte[] octets = etat.getByteArray("x509-certificate");
            if (octets == null) return false;
            X509Certificate x509 = (X509Certificate) CertificateFactory.getInstance("X.509")
                    .generateCertificate(new ByteArrayInputStream(octets));
            byte[] empreinte = MessageDigest.getInstance("SHA-256").digest(x509.getEncoded());
            StringBuilder hex = new StringBuilder();
            for (byte b : empreinte) {
                if (hex.length() > 0) hex.append(':');
                hex.append(String.format("%02X", b));
            }
            return hex.toString().equalsIgnoreCase(empreinteAttendue);
        } catch (Exception e) {
            Log.w("NgoniNana", "Verification du certificat impossible", e);
            return false;
        }
    }
}
