import com.atlassian.jira.issue.Issue;
import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;

public class JiraAgentTest {

    private JiraAgent jiraAgent;
    private Issue issue;

    @Before
    public void setUp() {
        jiraAgent = new JiraAgent();
        issue = new Issue();
    }

    @Test
    public void testDoExecuteSuccess() {
        // Caso de sucesso com valores válidos
        issue.setDescription("Atividade simulada pelo Java Agent");
        String result = jiraAgent.doExecute();
        assertEquals(SUCCESS, result);
    }

    @Test
    public void testDoExecuteError() {
        // Caso de erro (divisão por zero)
        try {
            jiraAgent.issue = null;
            jiraAgent.doExecute();
        } catch (Exception e) {
            assertEquals("Erro ao executar o Java Agent", e.getMessage());
        }
    }

    @Test
    public void testDoExecuteEdgeCase() {
        // Edge case (valores limite, strings vazias, None, etc)
        issue.setDescription(null);
        String result = jiraAgent.doExecute();
        assertEquals(SUCCESS, result);

        issue.setDescription("");
        result = jiraAgent.doExecute();
        assertEquals(SUCCESS, result);
    }
}