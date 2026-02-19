import com.atlassian.jira.plugin.webhook.WebHook;
import com.atlassian.jira.plugin.webhook.WebHookRequest;
import com.atlassian.jira.plugin.webhook.WebHookResponse;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

public class JavaAgentWebHookTest {

    public void testHandleSuccess() throws IOException {
        WebHookRequest request = new WebHookRequest();
        request.setContentType("application/json");
        request.setContent("{\"message\":\"Hello, World!\"}");

        JavaAgentWebHook webHook = new JavaAgentWebHook();
        WebHookResponse response = webHook.handle(request, null);

        assertEquals(200, response.getStatusCode());
        assertEquals("OK", response.getContent());
    }

    public void testHandleError() throws IOException {
        WebHookRequest request = new WebHookRequest();
        request.setContentType("application/json");
        request.setContent("{\"message\":\"Invalid message\"}");

        JavaAgentWebHook webHook = new JavaAgentWebHook();
        WebHookResponse response = webHook.handle(request, null);

        assertEquals(400, response.getStatusCode());
        assertEquals("Invalid message", response.getContent());
    }

    public void testHandleEdgeCase() throws IOException {
        WebHookRequest request = new WebHookRequest();
        request.setContentType("application/json");
        request.setContent("{\"message\":null}");

        JavaAgentWebHook webHook = new JavaAgentWebHook();
        WebHookResponse response = webHook.handle(request, null);

        assertEquals(400, response.getStatusCode());
        assertEquals("Invalid message", response.getContent());
    }
}