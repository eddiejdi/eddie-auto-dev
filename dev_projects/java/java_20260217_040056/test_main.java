import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class JiraAgentTest implements CommandLineRunner {

    @Autowired
    private Jira jira;

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private ProjectManager projectManager;

    @BeforeEach
    public void setUp() {
        // Configuração inicial para o teste
    }

    @Test
    public void testGetIssueByKeySuccess() throws Exception {
        String issueKey = "ABC-123";
        Issue issue = issueManager.getIssue(issueKey);
        assert issue != null : "Tarefa não encontrada.";
        System.out.println("Tarefa encontrada: " + issue.getKey());
        System.out.println("Status atual: " + issue.getStatus().getName());
    }

    @Test
    public void testGetIssueByKeyFailure() throws Exception {
        String issueKey = "XYZ-456";
        Issue issue = issueManager.getIssue(issueKey);
        assert issue == null : "Tarefa encontrada.";
        System.out.println("Tarefa não encontrada.");
    }
}