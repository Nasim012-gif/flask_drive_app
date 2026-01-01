import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ScrollView, Image, Alert, ActivityIndicator } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';

const SERVER_URL = 'https://nasim-event-app-2025.onrender.com';

export default function ManualUploadScreen({ navigation }) {
    const [selectedPhotos, setSelectedPhotos] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
    const [authToken, setAuthToken] = useState(null);

    // Get auth token from storage
    React.useEffect(() => {
        const loadToken = async () => {
            const token = await AsyncStorage.getItem('authToken');
            setAuthToken(token);
        };
        loadToken();
    }, []);

    // Request Photo Library Permission
    const requestPermissions = async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
            Alert.alert('Permission Required', 'Please allow access to your photos.');
            return false;
        }
        return true;
    };

    // Open Photo Gallery Picker
    const pickPhotos = async () => {
        const hasPermission = await requestPermissions();
        if (!hasPermission) return;

        let result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsMultipleSelection: true,
            quality: 0.8,
            selectionLimit: 100,
        });

        if (!result.canceled) {
            setSelectedPhotos(result.assets);
        }
    };

    // Upload Photos to Cloudinary via Backend
    const uploadToCloudinary = async () => {
        if (!authToken) {
            Alert.alert('Login Required', 'Please log in first.');
            navigation.navigate('Login');
            return;
        }

        if (selectedPhotos.length === 0) {
            Alert.alert('No Photos', 'Please select photos to upload.');
            return;
        }

        setUploading(true);
        setUploadProgress({ current: 0, total: selectedPhotos.length });

        try {
            const eventName = `Event_${new Date().getTime()}`;
            const photoUrls = [];

            // Upload each photo to backend (which uploads to Cloudinary)
            for (let i = 0; i < selectedPhotos.length; i++) {
                const photo = selectedPhotos[i];

                // Create FormData for multipart/form-data upload
                const formData = new FormData();
                formData.append('photo', {
                    uri: photo.uri,
                    type: 'image/jpeg',
                    name: photo.fileName || `photo_${Date.now()}.jpg`,
                });
                formData.append('event_name', eventName);

                const response = await fetch(`${SERVER_URL}/api/upload/manual`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                    },
                    body: formData,
                });

                const data = await response.json();
                if (data.url) {
                    photoUrls.push(data.public_id);
                }

                setUploadProgress({ current: i + 1, total: selectedPhotos.length });
            }

            // Create event with Cloudinary photos
            const eventResponse = await fetch(`${SERVER_URL}/api/events/manual`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    name: eventName,
                    photo_ids: photoUrls,
                    photo_count: selectedPhotos.length,
                })
            });

            const eventData = await eventResponse.json();

            setUploading(false);
            Alert.alert('Success!', `QR Code generated! Event ID: ${eventData.event_id}`);
            // Navigate back or to event details
            navigation.goBack();

        } catch (error) {
            setUploading(false);
            Alert.alert('Upload Failed', error.message);
        }
    };

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={styles.header}>
                <Text style={styles.title}>📸 Manual Upload</Text>
                <Text style={styles.subtitle}>Select photos from your camera roll</Text>
            </View>

            {/* Photo Picker */}
            {authToken && !uploading && (
                <TouchableOpacity style={styles.pickerBtn} onPress={pickPhotos}>
                    <Text style={styles.pickerBtnText}>
                        {selectedPhotos.length > 0
                            ? `✓ ${selectedPhotos.length} Photos Selected`
                            : '+ Select Photos'}
                    </Text>
                </TouchableOpacity>
            )}

            {!authToken && (
                <Text style={{ textAlign: 'center', color: '#6c757d', marginTop: 20 }}>
                    Please log in to upload photos
                </Text>
            )}

            {/* Photo Grid */}
            {selectedPhotos.length > 0 && !uploading && (
                <ScrollView style={styles.photoGrid}>
                    <View style={styles.gridContainer}>
                        {selectedPhotos.map((photo, index) => (
                            <Image key={index} source={{ uri: photo.uri }} style={styles.thumbnail} />
                        ))}
                    </View>
                </ScrollView>
            )}

            {/* Upload Button */}
            {selectedPhotos.length > 0 && !uploading && (
                <TouchableOpacity style={styles.uploadBtn} onPress={uploadToCloudinary}>
                    <Text style={styles.uploadBtnText}>🚀 Upload & Generate QR</Text>
                </TouchableOpacity>
            )}

            {/* Upload Progress */}
            {uploading && (
                <View style={styles.progressContainer}>
                    <ActivityIndicator size="large" color="#667eea" />
                    <Text style={styles.progressText}>
                        Uploading {uploadProgress.current}/{uploadProgress.total} photos...
                    </Text>
                    <View style={styles.progressBar}>
                        <View
                            style={[styles.progressFill, {
                                width: `${(uploadProgress.current / uploadProgress.total) * 100}%`
                            }]}
                        />
                    </View>
                </View>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#f8f9fa',
        padding: 20,
    },
    header: {
        marginBottom: 30,
        marginTop: 40,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#1a1a2e',
        marginBottom: 8,
    },
    subtitle: {
        fontSize: 16,
        color: '#6c757d',
    },
    pickerBtn: {
        backgroundColor: '#667eea',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginBottom: 20,
    },
    pickerBtnText: {
        color: 'white',
        fontSize: 16,
        fontWeight: '600',
    },
    photoGrid: {
        flex: 1,
        marginBottom: 20,
    },
    gridContainer: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
    },
    thumbnail: {
        width: '31%',
        aspectRatio: 1,
        borderRadius: 8,
        marginBottom: 8,
    },
    uploadBtn: {
        backgroundColor: '#28a745',
        padding: 18,
        borderRadius: 12,
        alignItems: 'center',
    },
    uploadBtnText: {
        color: 'white',
        fontSize: 18,
        fontWeight: 'bold',
    },
    progressContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    progressText: {
        fontSize: 18,
        color: '#1a1a2e',
        marginTop: 20,
        marginBottom: 20,
    },
    progressBar: {
        width: '100%',
        height: 8,
        backgroundColor: '#e9ecef',
        borderRadius: 4,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        backgroundColor: '#667eea',
    },
});
