import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

import java.util.List;

public class JavaAgentJiraIntegrator {

    private Jira jira;
    private IssueManager issueManager;
    private ProjectManager projectManager;

    public JavaAgentJiraIntegrator() {
        // Configuração do Jira
        this.jira = new Jira();
        this.issueManager = jira.getIssueManager();
        this.projectManager = jira.getProjectManager();
    }

    public void registerEvent(String eventType, String eventDescription) {
        try {
            Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY");
            Issue issue = issueManager.createIssue(project.getId(), "Event", eventDescription);
            System.out.println("Event registered: " + issue.getKey());
        } catch (Exception e) {
            System.err.println("Error registering event: " + e.getMessage());
        }
    }

    public void monitorActivity(String activityName, String activityDescription) {
        try {
            Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY");
            Issue issue = issueManager.createIssue(project.getId(), "Activity", activityDescription);
            System.out.println("Activity monitored: " + issue.getKey());
        } catch (Exception e) {
            System.err.println("Error monitoring activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegrator integrator = new JavaAgentJiraIntegrator();

        // Exemplo de registro de evento
        integrator.registerEvent("User Login", "User logged in from IP address 192.168.1.1");

        // Exemplo de monitoramento de atividade
        integrator.monitorActivity("System Update", "New version of the application is available");
    }
}