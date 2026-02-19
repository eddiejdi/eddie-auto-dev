import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.service.ServiceException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private IssueManager issueManager;

    public void trackActivity(String issueKey, String activityDescription) {
        try {
            Issue issue = issueManager.getIssueObject(issueKey);
            if (issue != null) {
                // Simulando a criação de um log de atividade no Jira
                System.out.println("Tracking activity for issue " + issueKey + ": " + activityDescription);
                // Aqui você poderia adicionar o código para salvar ou atualizar o log de atividade no Jira
            } else {
                System.err.println("Issue not found: " + issueKey);
            }
        } catch (ServiceException e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.trackActivity("JIRA-123", "User logged in");
    }
}