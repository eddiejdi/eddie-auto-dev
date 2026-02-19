import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.web.action.JiraActionSupport;

import javax.servlet.http.HttpServletRequest;
import java.util.HashMap;
import java.util.Map;

public class JavaAgentJiraIntegration extends JiraActionSupport {

    private ProjectManager projectManager;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;

    public JavaAgentJiraIntegration(ProjectManager projectManager, FieldManager fieldManager, CustomFieldManager customFieldManager) {
        this.projectManager = projectManager;
        this.fieldManager = fieldManager;
        this.customFieldManager = customFieldManager;
    }

    @Override
    protected String doExecute() throws Exception {
        // Simulate a Java Agent integration with Jira
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY");
        Issue issue = project.createIssue();
        TextField summaryField = fieldManager.getFieldByName("summary");
        TextField descriptionField = fieldManager.getFieldByName("description");

        Map<String, Object> issueFields = new HashMap<>();
        issueFields.put(summaryField.getName(), "Java Agent Integration with Jira");
        issueFields.put(descriptionField.getName(), "This is a test issue created by the Java Agent integration with Jira.");

        issue.setFields(issueFields);

        // Save the issue
        serviceContext.setCurrentUser(getUser());
        issueManager.updateIssue(serviceContext, issue, false);

        return SUCCESS;
    }
}