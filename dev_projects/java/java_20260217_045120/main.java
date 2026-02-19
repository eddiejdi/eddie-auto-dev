import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.ExtensionPoint;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
@ExtensionPoint
public class JavaAgentJiraIntegrator {

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private ProjectManager projectManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            Issue issue = issueManager.getIssueObject(issueKey);
            if (issue != null) {
                System.out.println("Tracking activity for issue: " + issue.getKey());
                // Simulando ação de atividade no Jira
                System.out.println("Activity logged: " + activity);
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity for issue: " + issueKey);
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegrator integrator = new JavaAgentJiraIntegrator();

        // Simulando ação de atividade
        integrator.trackActivity("ABC-123", "User logged in");
    }
}