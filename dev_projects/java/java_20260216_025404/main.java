import com.atlassian.jira.plugin.webhook.WebHook;
import com.atlassian.jira.plugin.webhook.WebHookRequest;
import com.atlassian.jira.plugin.webhook.WebHookResponse;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

public class JavaAgentWebHook implements WebHook {

    @Override
    public WebHookResponse handle(HttpServletRequest request, HttpServletResponse response) throws IOException {
        // Implementar a lógica para processar as requisições do Java Agent
        // Exemplo: Verificar se o corpo da requisição contém informações importantes

        // Simulação de um retorno com sucesso
        return new WebHookResponse(200, "OK");
    }

    public static void main(String[] args) {
        // Implementar a lógica para inicializar e configurar o web hook
        // Exemplo: Configurar o URL do web hook no Jira

        // Simulação de uma requisição do Java Agent
        WebHookRequest request = new WebHookRequest();
        request.setContentType("application/json");
        request.setContent("{\"message\":\"Hello, World!\"}");

        JavaAgentWebHook webHook = new JavaAgentWebHook();
        WebHookResponse response = webHook.handle(request, null);

        System.out.println(response.getStatusCode() + " - " + response.getContent());
    }
}