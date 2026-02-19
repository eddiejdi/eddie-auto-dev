import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.ProjectFieldManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.ExtensionPoint;
import com.atlassian.plugin.spring.scanner.annotation.Injector;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;
import com.atlassian.plugin.spring.scanner.annotation.SiteMap;

@Plugin("com.example.jiraagent")
@ComponentScan(basePackages = "com.example.jiraagent")
public class JiraAgent {

    @ExtensionPoint
    private ProjectFieldManager projectFieldManager;

    @ExtensionPoint
    private FieldManager fieldManager;

    @ExtensionPoint
    private CustomFieldManager customFieldManager;

    @ExtensionPoint
    private ProjectManager projectManager;

    public void monitorActivity(String issueKey) {
        try {
            Issue issue = projectManager.getIssue(issueKey);
            if (issue != null) {
                System.out.println("Monitoring issue: " + issue.getKey());
                // Add your monitoring logic here
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error monitoring issue: " + issueKey);
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JiraAgent agent = new JiraAgent();
        agent.monitorActivity("JRA-123");
    }
}