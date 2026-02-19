import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentImport;
import com.atlassian.sal.api.ApplicationProperties;
import com.atlassian.sal.api.TenantAccessor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @ComponentImport
    private ApplicationProperties applicationProperties;

    @ComponentImport
    private TenantAccessor tenantAccessor;

    @ComponentImport
    private Jira jira;

    @ComponentImport
    private IssueManager issueManager;

    @ComponentImport
    private FieldManager fieldManager;

    @ComponentImport
    private CustomFieldManager customFieldManager;

    @Autowired
    public JavaAgent() {
        // Constructor injection
    }

    public void registerEvent(String event) {
        try {
            JiraServiceContext serviceContext = new JiraServiceContext(jira, tenantAccessor);
            Issue issue = issueManager.createIssue(serviceContext, "Java Agent Event", "This is a test event from Java Agent", null, null, null, null, null);
            fieldManager.updateField(issue, customFieldManager.getCustomFieldByName("Event"), event);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.registerEvent("Test Event");
    }
}