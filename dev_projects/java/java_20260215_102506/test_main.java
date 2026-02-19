import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.util.JiraUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import static org.junit.jupiter.api.Assertions.*;

class JavaAgentTest {

    @Autowired
    private JiraUtils jiraUtils;

    private Issue issue;

    @BeforeEach
    public void setUp() {
        // Simula a obtenção de um issue existente
        issue = jiraUtils.getIssueByKey("YOUR_ISSUE_KEY");
    }

    @Test
    public void testTrackActivitySuccess() {
        String activity = "Novo comentário adicionado pelo Java Agent";
        javaAgent.trackActivity(issue, activity);
        assertNotNull(issue.getLastComment(), "Último comentário não foi adicionado ao issue");
        assertEquals(activity, issue.getLastComment().getText(), "Atividade incorreta no último comentário");
    }

    @Test
    public void testTrackActivityError() {
        String invalidActivity = "";
        assertThrows(IllegalArgumentException.class, () -> javaAgent.trackActivity(issue, invalidActivity));
        assertNull(issue.getLastComment(), "Último comentário não foi removido ao lançar exceção");
    }
}