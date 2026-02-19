import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.service.ServiceContextFactory;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private Jira jira;
    private JiraServiceContext serviceContext;

    @BeforeEach
    public void setUp() {
        jira = new Jira();
        serviceContext = ServiceContextFactory.getJiraServiceContext();
    }

    @Test
    public void testTrackActivitySuccess() throws Exception {
        String issueKey = "ABC-123";
        String activityDescription = "Tarefa concluída";

        jira.createIssue(serviceContext, issueKey, activityDescription);

        // Verificar se a atividade foi criada corretamente no Jira
        // Exemplo:
        // assertTrue(jira.getIssue(issueKey).getDescription().contains(activityDescription));
    }

    @Test
    public void testTrackActivityFailure() throws Exception {
        String issueKey = "ABC-123";
        String activityDescription = "";

        try {
            jira.createIssue(serviceContext, issueKey, activityDescription);
            fail("Deveria lançar uma exceção");
        } catch (Exception e) {
            // Verificar se a exceção é do tipo esperado
            assertTrue(e instanceof IllegalArgumentException || e.getMessage().contains("String vazia"));
        }
    }

    @Test
    public void testTrackActivityEdgeCase() throws Exception {
        String issueKey = "ABC-123";
        String activityDescription = null;

        try {
            jira.createIssue(serviceContext, issueKey, activityDescription);
            fail("Deveria lançar uma exceção");
        } catch (Exception e) {
            // Verificar se a exceção é do tipo esperado
            assertTrue(e instanceof IllegalArgumentException || e.getMessage().contains("Null"));
        }
    }

    @Test
    public void testTrackActivityInvalidInput() throws Exception {
        String issueKey = "ABC-123";
        String activityDescription = "Tarefa concluída";

        jira.createIssue(serviceContext, issueKey, activityDescription);

        // Verificar se a atividade foi criada corretamente no Jira
        // Exemplo:
        // assertTrue(jira.getIssue(issueKey).getDescription().contains(activityDescription));
    }
}