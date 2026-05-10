"""Test fixture for property scanner."""


class Contract:
    """Test model with various property types."""
    
    # Class-level variable
    portal_link_id = None
    status: str = "active"
    
    def __init__(self):
        # Instance variable
        self.created_at = None
        self.updated_at = None
    
    @property
    def portal_link(self):
        """Getter with no setter (orphaned)."""
        return self.portal_link_id
    
    @property
    def full_status(self):
        """Getter with setter."""
        return f"Status: {self.status}"
    
    @full_status.setter
    def full_status(self, value):
        """Setter for full_status."""
        self.status = value.replace("Status: ", "")
    
    def process(self):
        """Method that reads multiple properties."""
        link = self.portal_link
        status = self.status
        created = self.created_at
        return f"{link} {status} {created}"
    
    def update_status(self):
        """Method that writes a property."""
        self.status = "updated"


def standalone_function(contract):
    """Standalone function that reads a property on an object."""
    return contract.portal_link
