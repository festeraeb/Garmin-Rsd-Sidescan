"""
RSD Studio License Administration Tool
Simple GUI for generating and managing license keys
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from license_generator import LicenseGenerator
import pyperclip  # For copying to clipboard

class LicenseAdminGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RSD Studio License Administration")
        self.root.geometry("800x600")
        
        self.generator = LicenseGenerator()
        self.create_ui()
    
    def create_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🔑 RSD Studio License Administration", 
                              font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.pack(pady=15)
        
        # Main content
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        # License generation form
        form_frame = tk.LabelFrame(main_frame, text="Generate License Key", font=("Arial", 12, "bold"))
        form_frame.pack(fill="x", pady=(0, 20))
        
        # License type
        tk.Label(form_frame, text="License Type:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.license_type = ttk.Combobox(form_frame, values=["SAR", "COMMERCIAL", "ACADEMIC"], state="readonly")
        self.license_type.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
        self.license_type.set("SAR")
        
        # Organization
        tk.Label(form_frame, text="Organization:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.organization = tk.Entry(form_frame, font=("Arial", 10))
        self.organization.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        
        # Email
        tk.Label(form_frame, text="Email:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.email = tk.Entry(form_frame, font=("Arial", 10))
        self.email.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        
        # Purchase ID (for commercial)
        tk.Label(form_frame, text="Purchase ID:", font=("Arial", 10)).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.purchase_id = tk.Entry(form_frame, font=("Arial", 10))
        self.purchase_id.grid(row=3, column=1, sticky="ew", padx=10, pady=5)
        
        # Generate button
        generate_btn = tk.Button(form_frame, text="Generate License Key", 
                               command=self.generate_license, font=("Arial", 10, "bold"),
                               bg="#27ae60", fg="white", padx=20, pady=5)
        generate_btn.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        
        # Results area
        results_frame = tk.LabelFrame(main_frame, text="Generated License", font=("Arial", 12, "bold"))
        results_frame.pack(fill="both", expand=True)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, font=("Courier", 10), 
                                                     wrap=tk.WORD, height=15)
        self.results_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Buttons frame
        buttons_frame = tk.Frame(results_frame)
        buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        copy_btn = tk.Button(buttons_frame, text="Copy License Key", 
                           command=self.copy_license_key, font=("Arial", 10),
                           bg="#3498db", fg="white", padx=15, pady=5)
        copy_btn.pack(side="left", padx=(0, 10))
        
        copy_all_btn = tk.Button(buttons_frame, text="Copy All Details", 
                               command=self.copy_all_details, font=("Arial", 10),
                               bg="#9b59b6", fg="white", padx=15, pady=5)
        copy_all_btn.pack(side="left", padx=(0, 10))
        
        clear_btn = tk.Button(buttons_frame, text="Clear", 
                            command=self.clear_results, font=("Arial", 10),
                            bg="#95a5a6", fg="white", padx=15, pady=5)
        clear_btn.pack(side="right")
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready to generate license keys")
        status_bar = tk.Label(self.root, textvariable=self.status_var, 
                            relief=tk.SUNKEN, anchor="w", font=("Arial", 9))
        status_bar.pack(side="bottom", fill="x")
        
        self.last_license_key = ""
        self.last_full_details = ""
    
    def generate_license(self):
        # Get form data
        license_type = self.license_type.get()
        organization = self.organization.get().strip()
        email = self.email.get().strip()
        purchase_id = self.purchase_id.get().strip()
        
        # Validate inputs
        if not license_type:
            messagebox.showerror("Error", "Please select a license type")
            return
        
        if not organization:
            messagebox.showerror("Error", "Please enter organization name")
            return
            
        if not email:
            messagebox.showerror("Error", "Please enter email address")
            return
        
        try:
            # Generate license key
            if license_type == "SAR":
                license_key = self.generator.generate_sar_key(organization, email)
                features = [
                    "• Permanent free license for Search & Rescue operations",
                    "• All target detection features",
                    "• Priority support",
                    "• Specialized SAR algorithms"
                ]
            elif license_type == "COMMERCIAL":
                license_key = self.generator.generate_commercial_key(organization, email, purchase_id)
                features = [
                    "• Permanent commercial license",
                    "• All features including commercial use rights",
                    "• Priority support", 
                    "• Advanced algorithms",
                    "• Custom development options"
                ]
            elif license_type == "ACADEMIC":
                license_key = self.generator.generate_academic_key(organization, email)
                features = [
                    "• 1-year renewable academic license",
                    "• All features except commercial use",
                    "• Research tools and documentation",
                    "• Educational support"
                ]
            
            # Format results
            result_text = f"{license_type} License Generated Successfully!\n"
            result_text += "=" * 50 + "\n\n"
            result_text += f"Organization: {organization}\n"
            result_text += f"Email: {email}\n"
            if license_type == "COMMERCIAL" and purchase_id:
                result_text += f"Purchase ID: {purchase_id}\n"
            result_text += f"\nLicense Key: {license_key}\n\n"
            result_text += "Features included:\n"
            for feature in features:
                result_text += f"{feature}\n"
            
            result_text += "\n" + "=" * 50 + "\n"
            result_text += "Email Template:\n"
            result_text += "-" * 20 + "\n"
            result_text += f"Subject: RSD Studio {license_type} License Key\n\n"
            result_text += f"Dear {organization},\n\n"
            result_text += f"Your RSD Studio Professional {license_type} license has been generated.\n\n"
            result_text += f"License Key: {license_key}\n\n"
            result_text += "To activate your license:\n"
            result_text += "1. Launch RSD Studio Professional\n"
            result_text += "2. Go to License menu → Activate License Key\n"
            result_text += "3. Enter the license key above\n"
            result_text += "4. Enter your organization name and email\n\n"
            result_text += "Features included in your license:\n"
            for feature in features:
                result_text += f"{feature}\n"
            result_text += "\nThank you for using RSD Studio Professional!\n\n"
            result_text += "Support: festeraeb@gmail.com"
            
            # Display results
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(1.0, result_text)
            
            # Store for copying
            self.last_license_key = license_key
            self.last_full_details = result_text
            
            self.status_var.set(f"{license_type} license key generated successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate license key: {str(e)}")
            self.status_var.set("Error generating license key")
    
    def copy_license_key(self):
        if self.last_license_key:
            try:
                pyperclip.copy(self.last_license_key)
                self.status_var.set("License key copied to clipboard")
            except:
                # Fallback if pyperclip not available
                self.root.clipboard_clear()
                self.root.clipboard_append(self.last_license_key)
                self.status_var.set("License key copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No license key to copy")
    
    def copy_all_details(self):
        if self.last_full_details:
            try:
                pyperclip.copy(self.last_full_details)
                self.status_var.set("All details copied to clipboard")
            except:
                # Fallback if pyperclip not available
                self.root.clipboard_clear()
                self.root.clipboard_append(self.last_full_details)
                self.status_var.set("All details copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No details to copy")
    
    def clear_results(self):
        self.results_text.delete(1.0, tk.END)
        self.last_license_key = ""
        self.last_full_details = ""
        self.status_var.set("Results cleared")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        import pyperclip
    except ImportError:
        print("Note: pyperclip not installed. Clipboard functionality will use basic tkinter clipboard.")
    
    app = LicenseAdminGUI()
    app.run()