import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.plugin.system.webhook.WebhookManager;
import com.atlassian.jira.user.ApplicationUser;
import com.atlassian.jira.util.I18nHelper;
import com.atlassian.jira.workflow.WorkflowManager;
import com.atlassian.jira.workflow.instance.TransitionInstance;
import com.atlassian.jira.workflow.instance.TransitionResult;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.ExtensionPoint;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;
import com.atlassian.plugin.spring.scanner.annotation.SiteComponent;

import java.util.List;

@Plugin("com.example.jiraagent")
@ComponentScan(basePackages = "com.example.jiraagent")
public class JiraAgent {

    private final WebhookManager webhookManager;
    private final WorkflowManager workflowManager;
    private final I18nHelper i18nHelper;

    public JiraAgent(WebhookManager webhookManager, WorkflowManager workflowManager, I18nHelper i18nHelper) {
        this.webhookManager = webhookManager;
        this.workflowManager = workflowManager;
        this.i18nHelper = i18nHelper;
    }

    @SiteComponent
    public void registerWebhooks() {
        // Implementação para registrar webhooks com Jira
    }

    @ExtensionPoint
    public void handleWebhook(TransitionInstance transitionInstance) {
        try {
            ApplicationUser user = workflowManager.getUser(transitionInstance.getWorkflowContext().getWorkflowContext());
            if (user != null) {
                String issueKey = transitionInstance.getIssue().getKey();
                // Implementação para processar a tarefa após o webhook
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JiraAgent jiraAgent = new JiraAgent(new WebhookManager(), new WorkflowManager(), new I18nHelper());
        jiraAgent.registerWebhooks();
    }
}

// Testes unitários

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

public class JiraAgentTest {

    private JiraAgent jiraAgent;

    @BeforeEach
    public void setUp() {
        jiraAgent = new JiraAgent(new WebhookManager(), new WorkflowManager(), new I18nHelper());
    }

    @Test
    public void testRegisterWebhooksSuccess() {
        // Implementação para testar o registro de webhooks com sucesso
    }

    @Test
    public void testHandleWebhookSuccess() {
        // Implementação para testar a processamento da tarefa após o webhook com sucesso
    }

    @Test
    public void testHandleWebhookFailure() {
        // Implementação para testar a processamento da tarefa após o webhook com falha
    }
}