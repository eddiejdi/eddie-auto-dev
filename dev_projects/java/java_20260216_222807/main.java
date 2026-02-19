import com.atlassian.jira.service.JiraService;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.component.ComponentAccessor;

public class JavaAgentJiraIntegrator {

    private JiraService jiraService;
    private IssueManager issueManager;

    public JavaAgentJiraIntegrator() {
        this.jiraService = ComponentAccessor.getComponent(JiraService.class);
        this.issueManager = ComponentAccessor.getComponent(IssueManager.class);
    }

    public void integrateWithJavaAgent(String activity) {
        ServiceContext context = new ServiceContext();
        Issue issue = issueManager.createIssue(context, "JIRA-123", "Activity: " + activity);

        jiraService.updateIssue(context, issue, null);
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegrator integrator = new JavaAgentJiraIntegrator();

        try {
            integrator.integrateWithJavaAgent("Executing a task in Java");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}